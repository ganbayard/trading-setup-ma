import logging
import asyncio
from datetime import datetime
from typing import Optional, List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from PyQt5.QtCore import QObject, pyqtSignal

from update_market_asset_bar import update_crypto_data
from update_market_asset_bar_ib import update_market_data
from config import TIMEFRAMES

logger = logging.getLogger(__name__)

class MarketScheduler(QObject):
    """
    A scheduler service that manages market data updates and integrates with PyQt.
    """
    update_complete = pyqtSignal(str)  # Signal emitted when update is complete
    update_error = pyqtSignal(str)     # Signal emitted when update fails

    def __init__(self):
        super().__init__()
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_listener(self._job_listener, 
                                  EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        self.active_jobs = {}
        self._shutdown = False

    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self._shutdown = False
            self.scheduler.start()
            logger.info("Market scheduler started")

    def stop(self):
        """Stop the scheduler gracefully"""
        try:
            self._shutdown = True
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                logger.info("Market scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {str(e)}")

    def _job_listener(self, event):
        """Handle job execution events"""
        if self._shutdown:
            return
            
        if event.exception:
            logger.error(f"Job failed: {event.job_id}, Error: {str(event.exception)}")
            self.update_error.emit(f"Update failed for {event.job_id}: {str(event.exception)}")
        else:
            logger.info(f"Job completed successfully: {event.job_id}")
            self.update_complete.emit(event.job_id)

    def _load_crypto_symbols(self) -> List[str]:
        """Load crypto symbols from file"""
        try:
            with open('symbols/market_assets/crypto.txt', 'r') as f:
                return [symbol.strip() for symbol in f.read().strip().split(',')]
        except Exception as e:
            logger.error(f"Error loading crypto symbols: {str(e)}")
            return ['BTCUSDT']  # Default to BTC if file can't be read

    async def _run_crypto_update(self):
        """Wrapper for crypto update to handle async execution"""
        if self._shutdown:
            return
            
        try:
            symbols = self._load_crypto_symbols()
            logger.info(f"Running crypto update for symbols: {symbols}")
            await update_crypto_data(symbols, TIMEFRAMES)
        except Exception as e:
            logger.error(f"Error in crypto update: {str(e)}")
            raise

    async def _run_market_update(self, asset_type: str):
        """Wrapper for market update to handle async execution"""
        if self._shutdown:
            return
            
        try:
            await update_market_data(
                asset_type=asset_type,
                symbols=None,  # Will load from file
                timeframes=TIMEFRAMES,
                days_back=1
            )
        except Exception as e:
            logger.error(f"Error in {asset_type} update: {str(e)}")
            raise

    def _run_async_job(self, coro):
        """Helper to run async jobs in the scheduler"""
        if self._shutdown:
            return
            
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def schedule_crypto_update(self, interval_minutes: int = 5):
        """Schedule crypto market data updates"""
        job_id = 'crypto_update'
        
        if job_id in self.active_jobs:
            self.scheduler.remove_job(job_id)
        
        self.scheduler.add_job(
            lambda: self._run_async_job(self._run_crypto_update()),
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=job_id,
            name="Crypto Market Update",
            replace_existing=True,
            max_instances=1  # Prevent overlapping executions
        )
        self.active_jobs[job_id] = interval_minutes
        logger.info(f"Scheduled crypto update every {interval_minutes} minutes")

    def schedule_market_update(self, asset_type: str, schedule: str = "0 17 * * 1-5"):
        """
        Schedule market data updates using cron expression
        Default: Run at 5 PM (17:00) Monday through Friday
        """
        job_id = f'{asset_type.lower()}_update'
        
        if job_id in self.active_jobs:
            self.scheduler.remove_job(job_id)
        
        self.scheduler.add_job(
            lambda: self._run_async_job(self._run_market_update(asset_type)),
            trigger=CronTrigger.from_crontab(schedule),
            id=job_id,
            name=f"{asset_type} Market Update",
            replace_existing=True,
            max_instances=1  # Prevent overlapping executions
        )
        self.active_jobs[job_id] = schedule
        logger.info(f"Scheduled {asset_type} update with cron schedule: {schedule}")

    def get_next_run_time(self, job_id: str) -> Optional[datetime]:
        """Get the next scheduled run time for a job"""
        job = self.scheduler.get_job(job_id)
        return job.next_run_time if job else None

    def modify_schedule(self, job_id: str, new_interval: int = None, new_cron: str = None):
        """Modify an existing schedule"""
        if job_id not in self.active_jobs:
            raise ValueError(f"No job found with id: {job_id}")

        if new_interval is not None:
            self.scheduler.reschedule_job(
                job_id,
                trigger=IntervalTrigger(minutes=new_interval)
            )
            self.active_jobs[job_id] = new_interval
            logger.info(f"Modified {job_id} to run every {new_interval} minutes")
        
        elif new_cron is not None:
            self.scheduler.reschedule_job(
                job_id,
                trigger=CronTrigger.from_crontab(new_cron)
            )
            self.active_jobs[job_id] = new_cron
            logger.info(f"Modified {job_id} to run with cron schedule: {new_cron}")

    def pause_job(self, job_id: str):
        """Pause a scheduled job"""
        self.scheduler.pause_job(job_id)
        logger.info(f"Paused job: {job_id}")

    def resume_job(self, job_id: str):
        """Resume a paused job"""
        self.scheduler.resume_job(job_id)
        logger.info(f"Resumed job: {job_id}")

    def remove_job(self, job_id: str):
        """Remove a scheduled job"""
        if job_id in self.active_jobs:
            self.scheduler.remove_job(job_id)
            del self.active_jobs[job_id]
            logger.info(f"Removed job: {job_id}")
