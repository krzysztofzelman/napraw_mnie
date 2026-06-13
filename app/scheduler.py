"""
Harmonogram zadań — APScheduler.
Uruchamiany w lifespan aplikacji (main.py).
Zadania:
  - auto_complete_past_bookings: oznacza przeszłe rezerwacje jako zakończone
  - send_reminder_emails: wysyła przypomnienia o rezerwacjach na następny dzień
"""
import datetime
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.models import Booking, Provider
from app.email_mock import send_booking_reminder_email

logger = logging.getLogger("rezerwuj.scheduler")

scheduler = AsyncIOScheduler()


def auto_complete_past_bookings():
    """Oznacza przeszłe rezerwacje jako zakończone (codziennie 3:00)."""
    db = SessionLocal()
    try:
        today = datetime.date.today()
        past_bookings = (
            db.query(Booking)
            .filter(
                Booking.booking_date < today,
                Booking.status == "confirmed",
            )
            .all()
        )
        count = 0
        for b in past_bookings:
            b.status = "completed"
            count += 1
        if count:
            db.commit()
            logger.info("Auto-completed %d past booking(s)", count)
    except Exception as e:
        logger.error("Auto-complete error: %s", e)
    finally:
        db.close()


def send_reminder_emails():
    """Wysyła przypomnienia o rezerwacjach na następny dzień (codziennie 8:00)."""
    db = SessionLocal()
    try:
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        upcoming = (
            db.query(Booking)
            .filter(
                Booking.booking_date == tomorrow,
                Booking.status == "confirmed",
                Booking.client_email != "",
            )
            .all()
        )
        count = 0
        for b in upcoming:
            provider = db.query(Provider).filter(Provider.id == b.provider_id).first()
            if provider and b.client_email:
                date_str = b.booking_date.strftime("%d.%m.%Y")
                time_str = b.booking_time.strftime("%H:%M")
                send_booking_reminder_email(
                    b.client_email,
                    b.client_name,
                    provider.name,
                    date_str,
                    time_str,
                    provider.company_name,
                )
                count += 1
        if count:
            logger.info("Sent %d reminder email(s)", count)
    except Exception as e:
        logger.error("Reminder email error: %s", e)
    finally:
        db.close()


def start_scheduler():
    """Rejestruje zadania i uruchamia scheduler."""
    if scheduler.get_jobs():
        logger.warning("Scheduler już uruchomiony")
        return

    scheduler.add_job(
        auto_complete_past_bookings,
        CronTrigger(hour=3, minute=0),
        id="auto_complete",
        name="Auto-complete past bookings",
        replace_existing=True,
    )
    scheduler.add_job(
        send_reminder_emails,
        CronTrigger(hour=8, minute=0),
        id="send_reminders",
        name="Send booking reminders",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("APScheduler uruchomiony (auto-complete 3:00, reminders 8:00)")


def stop_scheduler():
    """Zatrzymuje scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler zatrzymany")
