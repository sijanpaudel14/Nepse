"""
Job Scheduler for NEPSE AI Trading Bot.

Automates daily analysis runs during market hours.

NEPSE Market Hours:
- Trading Days: Sunday to Thursday
- Pre-Open: 10:30 AM - 11:00 AM NPT
- Continuous Trading: 11:00 AM - 3:00 PM NPT
- Closed: Friday & Saturday, Public Holidays

Best times to run analysis:
- Pre-market (10:30 AM): Prepare for the day
- Post-market (3:30 PM): Generate signals for next day
"""

from datetime import datetime, time, timedelta
from typing import Callable, List, Optional
import pytz
from loguru import logger

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    logger.warning("APScheduler not installed. Scheduling disabled.")

from core.config import settings


# Nepal Time Zone
NPT = pytz.timezone("Asia/Kathmandu")


def is_nepse_trading_day(dt: datetime = None) -> bool:
    """
    Check if the given date is a NEPSE trading day.
    
    NEPSE is open Sunday-Thursday, closed Friday-Saturday.
    Does NOT account for public holidays (would need a holiday calendar).
    
    Args:
        dt: Date to check (default: today in NPT)
        
    Returns:
        True if trading day
    """
    if dt is None:
        dt = datetime.now(NPT)
    
    # Friday = 4, Saturday = 5 in Python (Monday = 0)
    # In Nepal: Friday & Saturday are weekends
    weekday = dt.weekday()
    return weekday not in [4, 5]


def is_market_hours(dt: datetime = None) -> bool:
    """
    Check if currently within NEPSE market hours.
    
    Market hours: 11:00 AM - 3:00 PM NPT
    
    Args:
        dt: Datetime to check (default: now in NPT)
        
    Returns:
        True if within market hours
    """
    if dt is None:
        dt = datetime.now(NPT)
    
    if not is_nepse_trading_day(dt):
        return False
    
    current_time = dt.time()
    market_open = time(11, 0)
    market_close = time(15, 0)
    
    return market_open <= current_time <= market_close


def get_next_market_open() -> datetime:
    """
    Get the next market open datetime.
    
    Returns:
        Datetime of next market open in NPT
    """
    now = datetime.now(NPT)
    
    # Start from tomorrow if market is closed today
    if not is_nepse_trading_day(now) or now.time() > time(15, 0):
        check_date = now + timedelta(days=1)
    else:
        check_date = now
    
    # Find next trading day
    while not is_nepse_trading_day(check_date):
        check_date += timedelta(days=1)
    
    # Set to market open time (11:00 AM)
    return check_date.replace(hour=11, minute=0, second=0, microsecond=0)


class TradingScheduler:
    """
    Scheduler for automated trading analysis.
    
    Runs jobs at optimal times for NEPSE trading.
    """
    
    def __init__(self):
        """Initialize the scheduler."""
        if not SCHEDULER_AVAILABLE:
            raise ImportError("APScheduler required. Run: pip install apscheduler")
        
        self.scheduler = BackgroundScheduler(timezone=NPT)
        self._setup_error_handling()
        self.jobs = []
    
    def _setup_error_handling(self):
        """Set up error handling for scheduled jobs."""
        def job_listener(event):
            if event.exception:
                logger.error(f"Scheduled job failed: {event.job_id}")
                logger.exception(event.exception)
            else:
                logger.info(f"Scheduled job completed: {event.job_id}")
        
        self.scheduler.add_listener(
            job_listener, 
            EVENT_JOB_ERROR | EVENT_JOB_EXECUTED
        )
    
    def add_pre_market_job(self, func: Callable, hour: int = 10, minute: int = 30):
        """
        Add a pre-market analysis job.
        
        Runs before market opens (default: 10:30 AM NPT).
        
        Args:
            func: Function to run
            hour: Hour to run (0-23)
            minute: Minute to run (0-59)
        """
        # Run Sunday-Thursday (NEPSE trading days)
        # Cron: day_of_week sun-thu
        job = self.scheduler.add_job(
            func,
            CronTrigger(
                day_of_week="sun-thu",
                hour=hour,
                minute=minute,
                timezone=NPT,
            ),
            id="pre_market_analysis",
            name="Pre-Market Analysis",
            replace_existing=True,
        )
        
        self.jobs.append(job)
        logger.info(f"Scheduled pre-market job: {hour:02d}:{minute:02d} NPT (Sun-Thu)")
    
    def add_post_market_job(self, func: Callable, hour: int = 15, minute: int = 30):
        """
        Add a post-market analysis job.
        
        Runs after market closes (default: 3:30 PM NPT).
        
        Args:
            func: Function to run
            hour: Hour to run (0-23)
            minute: Minute to run (0-59)
        """
        job = self.scheduler.add_job(
            func,
            CronTrigger(
                day_of_week="sun-thu",
                hour=hour,
                minute=minute,
                timezone=NPT,
            ),
            id="post_market_analysis",
            name="Post-Market Analysis",
            replace_existing=True,
        )
        
        self.jobs.append(job)
        logger.info(f"Scheduled post-market job: {hour:02d}:{minute:02d} NPT (Sun-Thu)")
    
    def add_interval_job(
        self, 
        func: Callable, 
        hours: int = 0, 
        minutes: int = 30,
        job_id: str = "interval_job",
    ):
        """
        Add an interval-based job (runs repeatedly).
        
        Args:
            func: Function to run
            hours: Hours between runs
            minutes: Minutes between runs
            job_id: Unique job identifier
        """
        job = self.scheduler.add_job(
            func,
            "interval",
            hours=hours,
            minutes=minutes,
            id=job_id,
            replace_existing=True,
        )
        
        self.jobs.append(job)
        logger.info(f"Scheduled interval job '{job_id}': every {hours}h {minutes}m")
    
    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
    
    def get_next_run_times(self) -> List[dict]:
        """
        Get next run times for all scheduled jobs.
        
        Returns:
            List of job info dicts
        """
        info = []
        for job in self.scheduler.get_jobs():
            info.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.strftime("%Y-%m-%d %H:%M:%S %Z") if job.next_run_time else None,
            })
        return info


def create_default_scheduler() -> TradingScheduler:
    """
    Create a scheduler with default NEPSE trading jobs.
    
    Returns:
        Configured TradingScheduler
    """
    from main import run_full_pipeline
    
    scheduler = TradingScheduler()
    
    # Pre-market: Fetch data and prepare (10:30 AM)
    def pre_market_job():
        logger.info("Running pre-market analysis...")
        from data.fetcher import NepseFetcher
        from core.database import init_db
        
        init_db()
        fetcher = NepseFetcher()
        
        try:
            # Just fetch data, don't run full pipeline
            df = fetcher.fetch_today_prices()
            logger.info(f"Pre-market: Fetched {len(df)} prices")
        except Exception as e:
            logger.error(f"Pre-market fetch failed: {e}")
    
    # Post-market: Full analysis and signals (3:30 PM)
    def post_market_job():
        logger.info("Running post-market analysis...")
        run_full_pipeline(dry_run=False)
    
    scheduler.add_pre_market_job(pre_market_job, hour=10, minute=30)
    scheduler.add_post_market_job(post_market_job, hour=15, minute=30)
    
    return scheduler


# Convenience functions

def run_scheduler():
    """Run the scheduler in the foreground (blocking)."""
    if not SCHEDULER_AVAILABLE:
        logger.error("APScheduler not installed")
        return
    
    scheduler = create_default_scheduler()
    scheduler.start()
    
    logger.info("Scheduler running. Press Ctrl+C to exit.")
    logger.info("Next runs:")
    for job in scheduler.get_next_run_times():
        logger.info(f"  {job['name']}: {job['next_run']}")
    
    try:
        # Keep the main thread alive
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down scheduler...")
        scheduler.stop()


if __name__ == "__main__":
    run_scheduler()
