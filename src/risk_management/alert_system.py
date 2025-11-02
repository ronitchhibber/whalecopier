"""
Alert and Notification System - Real-time alerts for risk events.

Features:
- Multi-channel notifications (console, file, webhook)
- Alert levels with prioritization
- Alert throttling to prevent spam
- Email notifications (optional)
- Slack/Discord webhooks (optional)
- SMS alerts for critical events (optional)
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, field
import aiohttp

from .risk_manager import RiskEvent, RiskLevel, RiskEventType

logger = logging.getLogger(__name__)


class AlertChannel(Enum):
    """Alert delivery channels"""
    CONSOLE = "console"
    FILE = "file"
    WEBHOOK = "webhook"
    EMAIL = "email"
    SMS = "sms"


class AlertPriority(Enum):
    """Alert priority levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AlertConfig:
    """Configuration for alert system"""

    # Enabled channels
    console_enabled: bool = True
    file_enabled: bool = True
    webhook_enabled: bool = False
    email_enabled: bool = False
    sms_enabled: bool = False

    # File logging
    alert_log_file: str = "logs/alerts.log"
    max_log_size_mb: int = 100

    # Webhook settings
    webhook_url: Optional[str] = None
    webhook_timeout_seconds: int = 5

    # Email settings
    email_smtp_host: Optional[str] = None
    email_smtp_port: int = 587
    email_from: Optional[str] = None
    email_to: List[str] = field(default_factory=list)
    email_password: Optional[str] = None

    # SMS settings (Twilio)
    sms_account_sid: Optional[str] = None
    sms_auth_token: Optional[str] = None
    sms_from_number: Optional[str] = None
    sms_to_numbers: List[str] = field(default_factory=list)

    # Throttling
    throttle_enabled: bool = True
    throttle_window_minutes: int = 15
    max_alerts_per_window: int = 10

    # Priority filtering
    min_priority: AlertPriority = AlertPriority.INFO
    critical_events_only_for_sms: bool = True


@dataclass
class Alert:
    """Alert message"""
    timestamp: datetime
    priority: AlertPriority
    title: str
    message: str
    event_type: Optional[RiskEventType] = None
    metrics: Dict = field(default_factory=dict)
    channels: List[AlertChannel] = field(default_factory=list)


class AlertThrottler:
    """Throttles alerts to prevent spam"""

    def __init__(self, window_minutes: int = 15, max_alerts: int = 10):
        self.window_minutes = window_minutes
        self.max_alerts = max_alerts
        self.alert_history: List[datetime] = []

    def should_send(self, alert: Alert) -> bool:
        """Check if alert should be sent based on throttling rules"""

        # Critical alerts always go through
        if alert.priority == AlertPriority.CRITICAL:
            return True

        # Clean old entries
        cutoff = datetime.utcnow() - timedelta(minutes=self.window_minutes)
        self.alert_history = [t for t in self.alert_history if t > cutoff]

        # Check limit
        if len(self.alert_history) >= self.max_alerts:
            logger.warning(f"Alert throttled: {len(self.alert_history)} alerts in last {self.window_minutes} minutes")
            return False

        # Record this alert
        self.alert_history.append(datetime.utcnow())
        return True


class ConsoleAlertHandler:
    """Sends alerts to console/logger"""

    def __init__(self):
        self.logger = logging.getLogger("AlertSystem")

    async def send(self, alert: Alert):
        """Send alert to console"""

        emoji_map = {
            AlertPriority.INFO: "ℹ️",
            AlertPriority.WARNING: "⚠️",
            AlertPriority.ERROR: "❌",
            AlertPriority.CRITICAL: "🚨"
        }

        emoji = emoji_map.get(alert.priority, "📢")
        msg = f"{emoji} [{alert.priority.value.upper()}] {alert.title}: {alert.message}"

        if alert.priority == AlertPriority.CRITICAL:
            self.logger.critical(msg)
        elif alert.priority == AlertPriority.ERROR:
            self.logger.error(msg)
        elif alert.priority == AlertPriority.WARNING:
            self.logger.warning(msg)
        else:
            self.logger.info(msg)


class FileAlertHandler:
    """Writes alerts to log file"""

    def __init__(self, log_file: str, max_size_mb: int = 100):
        self.log_file = log_file
        self.max_size_bytes = max_size_mb * 1024 * 1024

    async def send(self, alert: Alert):
        """Append alert to log file"""

        try:
            # Check file size and rotate if needed
            import os
            if os.path.exists(self.log_file):
                if os.path.getsize(self.log_file) > self.max_size_bytes:
                    # Rotate log
                    backup = f"{self.log_file}.1"
                    if os.path.exists(backup):
                        os.remove(backup)
                    os.rename(self.log_file, backup)

            # Ensure directory exists
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

            # Write alert
            with open(self.log_file, 'a') as f:
                alert_dict = {
                    "timestamp": alert.timestamp.isoformat(),
                    "priority": alert.priority.value,
                    "title": alert.title,
                    "message": alert.message,
                    "event_type": alert.event_type.value if alert.event_type else None,
                    "metrics": alert.metrics
                }
                f.write(json.dumps(alert_dict) + "\n")

        except Exception as e:
            logger.error(f"Failed to write alert to file: {e}")


class WebhookAlertHandler:
    """Sends alerts to webhook (Slack, Discord, custom endpoint)"""

    def __init__(self, webhook_url: str, timeout_seconds: int = 5):
        self.webhook_url = webhook_url
        self.timeout = timeout_seconds

    async def send(self, alert: Alert):
        """Send alert via webhook"""

        try:
            # Format payload based on webhook type
            if "slack.com" in self.webhook_url:
                payload = self._format_slack(alert)
            elif "discord.com" in self.webhook_url:
                payload = self._format_discord(alert)
            else:
                payload = self._format_generic(alert)

            # Send webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status not in [200, 204]:
                        logger.error(f"Webhook failed: {response.status}")

        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")

    def _format_slack(self, alert: Alert) -> Dict:
        """Format alert for Slack"""

        color_map = {
            AlertPriority.INFO: "#36a64f",
            AlertPriority.WARNING: "#ff9900",
            AlertPriority.ERROR: "#ff0000",
            AlertPriority.CRITICAL: "#990000"
        }

        return {
            "attachments": [{
                "color": color_map.get(alert.priority, "#808080"),
                "title": f"{alert.priority.value.upper()}: {alert.title}",
                "text": alert.message,
                "fields": [
                    {
                        "title": "Timestamp",
                        "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        "short": True
                    },
                    {
                        "title": "Priority",
                        "value": alert.priority.value.upper(),
                        "short": True
                    }
                ] + [
                    {
                        "title": k,
                        "value": str(v),
                        "short": True
                    }
                    for k, v in alert.metrics.items()
                ],
                "footer": "Whale Trader Risk Manager",
                "ts": int(alert.timestamp.timestamp())
            }]
        }

    def _format_discord(self, alert: Alert) -> Dict:
        """Format alert for Discord"""

        color_map = {
            AlertPriority.INFO: 3066993,
            AlertPriority.WARNING: 16776960,
            AlertPriority.ERROR: 16711680,
            AlertPriority.CRITICAL: 10038562
        }

        fields = [
            {
                "name": "Timestamp",
                "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "inline": True
            },
            {
                "name": "Priority",
                "value": alert.priority.value.upper(),
                "inline": True
            }
        ]

        for k, v in alert.metrics.items():
            fields.append({
                "name": k,
                "value": str(v),
                "inline": True
            })

        return {
            "embeds": [{
                "title": f"{alert.priority.value.upper()}: {alert.title}",
                "description": alert.message,
                "color": color_map.get(alert.priority, 8421504),
                "fields": fields,
                "footer": {
                    "text": "Whale Trader Risk Manager"
                },
                "timestamp": alert.timestamp.isoformat()
            }]
        }

    def _format_generic(self, alert: Alert) -> Dict:
        """Format alert for generic webhook"""
        return {
            "timestamp": alert.timestamp.isoformat(),
            "priority": alert.priority.value,
            "title": alert.title,
            "message": alert.message,
            "event_type": alert.event_type.value if alert.event_type else None,
            "metrics": alert.metrics
        }


class EmailAlertHandler:
    """Sends alerts via email"""

    def __init__(self, smtp_host: str, smtp_port: int, from_email: str,
                 to_emails: List[str], password: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.from_email = from_email
        self.to_emails = to_emails
        self.password = password

    async def send(self, alert: Alert):
        """Send alert via email"""

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ", ".join(self.to_emails)
            msg['Subject'] = f"[{alert.priority.value.upper()}] {alert.title}"

            # Body
            body = f"""
Whale Trader Risk Alert

Priority: {alert.priority.value.upper()}
Timestamp: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
Event Type: {alert.event_type.value if alert.event_type else 'N/A'}

{alert.message}

Metrics:
{json.dumps(alert.metrics, indent=2)}

---
Whale Trader Risk Management System
"""

            msg.attach(MIMEText(body, 'plain'))

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.from_email, self.password)
                server.send_message(msg)

            logger.info(f"Email alert sent to {len(self.to_emails)} recipients")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")


class SMSAlertHandler:
    """Sends alerts via SMS using Twilio"""

    def __init__(self, account_sid: str, auth_token: str,
                 from_number: str, to_numbers: List[str]):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.to_numbers = to_numbers

    async def send(self, alert: Alert):
        """Send alert via SMS"""

        try:
            from twilio.rest import Client

            client = Client(self.account_sid, self.auth_token)

            # Create SMS body (max 160 chars)
            body = f"[{alert.priority.value.upper()}] {alert.title}: {alert.message}"
            if len(body) > 160:
                body = body[:157] + "..."

            # Send to all numbers
            for number in self.to_numbers:
                message = client.messages.create(
                    body=body,
                    from_=self.from_number,
                    to=number
                )
                logger.info(f"SMS alert sent to {number}: {message.sid}")

        except ImportError:
            logger.error("Twilio library not installed. Install with: pip install twilio")
        except Exception as e:
            logger.error(f"Failed to send SMS alert: {e}")


class AlertSystem:
    """Main alert and notification system"""

    def __init__(self, config: Optional[AlertConfig] = None):
        self.config = config or AlertConfig()
        self.throttler = AlertThrottler(
            self.config.throttle_window_minutes,
            self.config.max_alerts_per_window
        ) if self.config.throttle_enabled else None

        # Initialize handlers
        self.handlers: Dict[AlertChannel, Callable] = {}

        if self.config.console_enabled:
            self.handlers[AlertChannel.CONSOLE] = ConsoleAlertHandler()

        if self.config.file_enabled:
            self.handlers[AlertChannel.FILE] = FileAlertHandler(
                self.config.alert_log_file,
                self.config.max_log_size_mb
            )

        if self.config.webhook_enabled and self.config.webhook_url:
            self.handlers[AlertChannel.WEBHOOK] = WebhookAlertHandler(
                self.config.webhook_url,
                self.config.webhook_timeout_seconds
            )

        if self.config.email_enabled and all([
            self.config.email_smtp_host,
            self.config.email_from,
            self.config.email_to,
            self.config.email_password
        ]):
            self.handlers[AlertChannel.EMAIL] = EmailAlertHandler(
                self.config.email_smtp_host,
                self.config.email_smtp_port,
                self.config.email_from,
                self.config.email_to,
                self.config.email_password
            )

        if self.config.sms_enabled and all([
            self.config.sms_account_sid,
            self.config.sms_auth_token,
            self.config.sms_from_number,
            self.config.sms_to_numbers
        ]):
            self.handlers[AlertChannel.SMS] = SMSAlertHandler(
                self.config.sms_account_sid,
                self.config.sms_auth_token,
                self.config.sms_from_number,
                self.config.sms_to_numbers
            )

        logger.info(f"AlertSystem initialized with {len(self.handlers)} handlers")

    async def send_alert(self, alert: Alert):
        """Send alert through all enabled channels"""

        # Check throttling
        if self.throttler and not self.throttler.should_send(alert):
            return

        # Check minimum priority
        priority_order = {
            AlertPriority.INFO: 0,
            AlertPriority.WARNING: 1,
            AlertPriority.ERROR: 2,
            AlertPriority.CRITICAL: 3
        }

        if priority_order[alert.priority] < priority_order[self.config.min_priority]:
            return

        # Determine channels
        channels = alert.channels if alert.channels else list(self.handlers.keys())

        # Filter SMS for critical only if configured
        if self.config.critical_events_only_for_sms and alert.priority != AlertPriority.CRITICAL:
            channels = [c for c in channels if c != AlertChannel.SMS]

        # Send to each channel
        tasks = []
        for channel in channels:
            if channel in self.handlers:
                handler = self.handlers[channel]
                tasks.append(handler.send(alert))

        # Execute all sends concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def send_risk_event(self, event: RiskEvent):
        """Send alert for a risk event"""

        # Map risk level to alert priority
        priority_map = {
            RiskLevel.LOW: AlertPriority.INFO,
            RiskLevel.MEDIUM: AlertPriority.WARNING,
            RiskLevel.HIGH: AlertPriority.ERROR,
            RiskLevel.CRITICAL: AlertPriority.CRITICAL
        }

        alert = Alert(
            timestamp=event.timestamp,
            priority=priority_map[event.risk_level],
            title=f"Risk Event: {event.event_type.value.replace('_', ' ').title()}",
            message=event.message,
            event_type=event.event_type,
            metrics=event.metrics
        )

        await self.send_alert(alert)

    async def send_custom_alert(
        self,
        priority: AlertPriority,
        title: str,
        message: str,
        metrics: Optional[Dict] = None
    ):
        """Send a custom alert"""

        alert = Alert(
            timestamp=datetime.utcnow(),
            priority=priority,
            title=title,
            message=message,
            metrics=metrics or {}
        )

        await self.send_alert(alert)

    async def test_all_channels(self):
        """Send test alert to all channels"""

        test_alert = Alert(
            timestamp=datetime.utcnow(),
            priority=AlertPriority.INFO,
            title="Alert System Test",
            message="This is a test alert from the Whale Trader risk management system.",
            metrics={
                "test_metric_1": "OK",
                "test_metric_2": 123,
                "test_metric_3": "All channels working"
            }
        )

        await self.send_alert(test_alert)
        logger.info("Test alert sent to all channels")


# Integration with Risk Manager

async def integrate_with_risk_manager(risk_manager, alert_system: AlertSystem):
    """Integrate alert system with risk manager"""

    original_halt = risk_manager.halt_trading

    def halt_with_alert(reason: str):
        """Halt trading and send critical alert"""
        original_halt(reason)

        asyncio.create_task(alert_system.send_custom_alert(
            AlertPriority.CRITICAL,
            "Trading Halted",
            reason,
            risk_manager._metrics_to_dict()
        ))

    risk_manager.halt_trading = halt_with_alert
    logger.info("Alert system integrated with risk manager")
