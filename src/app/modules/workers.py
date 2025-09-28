import asyncio
import logging
from typing import Optional, Tuple
from datetime import datetime

from ..config import settings
from .scraper import ScraperService
from .store import DatabaseService
from .models import TaskStatusEnum
from ..utils.image_service import ImageService

logger = logging.getLogger(__name__)


class WorkerManager:
    """Manages background workers for scraping tasks"""

    def __init__(
        self,
        task_queue: asyncio.Queue,
        scraper_service: ScraperService,
        db_service: DatabaseService,
    ):
        self.task_queue = task_queue
        self.scraper_service = scraper_service
        self.db_service = db_service
        self.workers = []
        self.active_workers = 0
        self.running = False

    async def start_workers(self):
        """Start background workers"""
        self.running = True

        for i in range(settings.WORKER_COUNT):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)

        logger.info(f"Started {settings.WORKER_COUNT} workers")

    async def stop_workers(self):
        """Stop all workers"""
        self.running = False

        # Cancel all workers
        for worker in self.workers:
            worker.cancel()

        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)

        # Close browser
        await self.scraper_service.close_browser()

        logger.info("All workers stopped")

    async def _worker(self, worker_name: str):
        """Individual worker that processes tasks from queue"""
        logger.info(f"{worker_name} started")

        while self.running:
            try:
                # Get task from queue with timeout
                try:
                    task_data = await asyncio.wait_for(
                        self.task_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                self.active_workers += 1

                # Unpack task data
                if len(task_data) == 3:
                    asin, marketplace, task_id = task_data
                else:
                    asin, marketplace = task_data
                    task_id = None

                logger.info(f"{worker_name} processing {asin} from {marketplace}")

                # Update task status to running
                if task_id:
                    await self.db_service.update_task_status(
                        task_id, TaskStatusEnum.RUNNING
                    )

                # Process the task
                await self._process_task(worker_name, asin, marketplace, task_id)

                # Mark task as done
                self.task_queue.task_done()

            except Exception as e:
                logger.error(f"{worker_name} error: {e}")

                # Update task status to failed
                if "task_id" in locals() and task_id:
                    await self.db_service.update_task_status(
                        task_id, TaskStatusEnum.FAILED, str(e)
                    )

            finally:
                self.active_workers = max(0, self.active_workers - 1)

        logger.info(f"{worker_name} stopped")

    async def _process_task(
        self, worker_name: str, asin: str, marketplace: str, task_id: Optional[str]
    ):
        """Process a single scraping task with retry logic"""
        last_error = None

        for attempt in range(settings.WORKER_RETRY_ATTEMPTS):
            try:
                logger.info(f"{worker_name} attempt {attempt + 1} for {asin}")

                # Scrape product
                scraped_data = await self.scraper_service.scrape_product(
                    asin, marketplace
                )

                # Save to database and check if content changed
                product_id, content_changed = await self.db_service.upsert_product(scraped_data)

                logger.info(
                    f"{worker_name} successfully scraped {asin} -> {product_id}, content_changed: {content_changed}"
                )

                # Only download images if content changed
                if content_changed:
                    logger.info(f"{worker_name} content changed, downloading images for {asin}")
                    await self._download_product_images(
                        worker_name, product_id, scraped_data
                    )
                else:
                    logger.info(f"{worker_name} content unchanged, skipping image download for {asin}")

                # Update task status to success
                if task_id:
                    await self.db_service.update_task_status(
                        task_id, TaskStatusEnum.SUCCESS
                    )

                return

            except Exception as e:
                last_error = e
                logger.warning(
                    f"{worker_name} attempt {attempt + 1} failed for {asin}: {e}"
                )

                if attempt < settings.WORKER_RETRY_ATTEMPTS - 1:
                    # Wait before retry
                    await asyncio.sleep(settings.WORKER_RETRY_DELAY * (attempt + 1))

        # All attempts failed
        logger.error(f"{worker_name} all attempts failed for {asin}: {last_error}")

        if task_id:
            await self.db_service.update_task_status(
                task_id, TaskStatusEnum.FAILED, str(last_error)
            )

        raise last_error

    async def _download_product_images(
        self, worker_name: str, product_id: str, scraped_data
    ):
        """Download and store product images"""
        try:
            async with ImageService(self.db_service) as image_service:
                logger.info(
                    f"{worker_name} downloading images for product {product_id}"
                )

                results = await image_service.download_and_store_images(
                    product_id, scraped_data
                )

                # Log results
                if results["hero_image"]:
                    logger.info(
                        f"{worker_name} hero image stored: {results['hero_image']['storage_path']}"
                    )

                if results["gallery_images"]:
                    logger.info(
                        f"{worker_name} stored {len(results['gallery_images'])} gallery images"
                    )

                if results["errors"]:
                    logger.warning(
                        f"{worker_name} image download errors: {results['errors']}"
                    )

        except Exception as e:
            logger.error(
                f"{worker_name} failed to download images for {product_id}: {e}"
            )
            # 不抛出异常，因为图片下载失败不应该导致整个任务失败
