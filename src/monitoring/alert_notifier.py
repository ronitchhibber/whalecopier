"""
Alert Notification System
Sends alerts via multiple channels (email, webhook, etc.)
"""

import asyncio
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional
from datetime import datetime
import logging
import json
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NotificationChannel:
    """Represents a notification channel configuration"""
    name: str
    type: str  # 'email', 'webhook', 'discord', 'slack', 'telegram'
    config: Dict
    enabled: bool = True
    severity_filter: List[str] = None  # Filter by severity levels


class AlertNotifier:
    """
    Multi-channel alert notification system
    Supports email, webhooks, Discord, Slack, Telegram
    """

    def __init__(self, channels: List[NotificationChannel] = None):
        self.channels = channels or []
        self.notification_history = []
        self.rate_limits = {}  # Track rate limits per channel

    def add_channel(self, channel: NotificationChannel):
        """Add a notification channel"""
        self.channels.append(channel)
        logger.info(f"Added notification channel: {channel.name} ({channel.type})")

    async def send_alert(self, alert: Dict) -> Dict[str, bool]:
        """
        Send alert through all configured channels
        Returns success status for each channel
        """
        results = {}

        for channel in self.channels:
            if not channel.enabled:
                continue

            # Check severity filter
            if channel.severity_filter:
                if alert.get("severity") not in channel.severity_filter:
                    continue

            # Check rate limiting
            if self._is_rate_limited(channel.name):
                logger.warning(f"Channel {channel.name} is rate limited")
                results[channel.name] = False
                continue

            # Send based on channel type
            try:
                if channel.type == "email":
                    success = await self._send_email(alert, channel.config)
                elif channel.type == "webhook":
                    success = await self._send_webhook(alert, channel.config)
                elif channel.type == "discord":
                    success = await self._send_discord(alert, channel.config)
                elif channel.type == "slack":
                    success = await self._send_slack(alert, channel.config)
                elif channel.type == "telegram":
                    success = await self._send_telegram(alert, channel.config)
                else:
                    logger.error(f"Unknown channel type: {channel.type}")
                    success = False

                results[channel.name] = success

                if success:
                    self._update_rate_limit(channel.name)
                    self._record_notification(channel.name, alert)

            except Exception as e:
                logger.error(f"Failed to send alert via {channel.name}: {e}")
                results[channel.name] = False

        return results

    async def _send_email(self, alert: Dict, config: Dict) -> bool:
        """Send email alert"""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = config['from_email']
            msg['To'] = config['to_email']
            msg['Subject'] = f"[{alert['severity'].upper()}] Whale Trading Alert: {alert['category']}"

            # Create body
            body = f"""
            Alert Time: {alert['timestamp']}
            Severity: {alert['severity']}
            Category: {alert['category']}

            Message: {alert['message']}

            Details:
            {json.dumps(alert.get('details', {}), indent=2)}

            ---
            Polymarket Whale Copy Trading System
            """

            msg.attach(MIMEText(body, 'plain'))

            # Send email
            with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
                if config.get('use_tls', True):
                    server.starttls()
                if config.get('username'):
                    server.login(config['username'], config['password'])
                server.send_message(msg)

            logger.info(f"Email alert sent to {config['to_email']}")
            return True

        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False

    async def _send_webhook(self, alert: Dict, config: Dict) -> bool:
        """Send webhook alert"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = config.get('headers', {})
                headers['Content-Type'] = 'application/json'

                payload = {
                    "timestamp": alert['timestamp'],
                    "severity": alert['severity'],
                    "category": alert['category'],
                    "message": alert['message'],
                    "details": alert.get('details', {})
                }

                async with session.post(
                    config['url'],
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"Webhook alert sent to {config['url']}")
                        return True
                    else:
                        logger.error(f"Webhook returned {resp.status}")
                        return False

        except Exception as e:
            logger.error(f"Webhook send failed: {e}")
            return False

    async def _send_discord(self, alert: Dict, config: Dict) -> bool:
        """Send Discord webhook alert"""
        try:
            # Format Discord embed
            color = {
                'info': 0x3498db,
                'warning': 0xf39c12,
                'error': 0xe74c3c,
                'critical': 0xc0392b
            }.get(alert['severity'], 0x95a5a6)

            embed = {
                "title": f"🚨 {alert['category'].upper()} Alert",
                "description": alert['message'],
                "color": color,
                "fields": [
                    {
                        "name": "Severity",
                        "value": alert['severity'].upper(),
                        "inline": True
                    },
                    {
                        "name": "Time",
                        "value": alert['timestamp'],
                        "inline": True
                    }
                ],
                "footer": {
                    "text": "Whale Copy Trading System"
                }
            }

            # Add details as fields
            for key, value in alert.get('details', {}).items():
                embed['fields'].append({
                    "name": key.replace('_', ' ').title(),
                    "value": str(value),
                    "inline": True
                })

            payload = {
                "embeds": [embed],
                "username": "Trading Bot",
                "avatar_url": "https://i.imgur.com/4M34hi2.png"  # Whale emoji
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(config['webhook_url'], json=payload) as resp:
                    if resp.status == 204:  # Discord returns 204 on success
                        logger.info("Discord alert sent")
                        return True
                    else:
                        logger.error(f"Discord webhook returned {resp.status}")
                        return False

        except Exception as e:
            logger.error(f"Discord send failed: {e}")
            return False

    async def _send_slack(self, alert: Dict, config: Dict) -> bool:
        """Send Slack webhook alert"""
        try:
            # Format Slack message
            icon = {
                'info': ':information_source:',
                'warning': ':warning:',
                'error': ':x:',
                'critical': ':rotating_light:'
            }.get(alert['severity'], ':bell:')

            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{icon} {alert['category'].upper()} Alert"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{alert['message']}*\n\n"
                               f"Severity: `{alert['severity']}`\n"
                               f"Time: {alert['timestamp']}"
                    }
                }
            ]

            # Add details
            if alert.get('details'):
                details_text = "\n".join([
                    f"• *{k}*: {v}"
                    for k, v in alert['details'].items()
                ])
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Details:*\n{details_text}"
                    }
                })

            payload = {"blocks": blocks}

            async with aiohttp.ClientSession() as session:
                async with session.post(config['webhook_url'], json=payload) as resp:
                    if resp.status == 200:
                        logger.info("Slack alert sent")
                        return True
                    else:
                        logger.error(f"Slack webhook returned {resp.status}")
                        return False

        except Exception as e:
            logger.error(f"Slack send failed: {e}")
            return False

    async def _send_telegram(self, alert: Dict, config: Dict) -> bool:
        """Send Telegram alert"""
        try:
            # Format Telegram message
            icon = {
                'info': 'ℹ️',
                'warning': '⚠️',
                'error': '❌',
                'critical': '🚨'
            }.get(alert['severity'], '📢')

            message = (
                f"{icon} <b>{alert['category'].upper()} Alert</b>\n\n"
                f"<b>Message:</b> {alert['message']}\n"
                f"<b>Severity:</b> {alert['severity']}\n"
                f"<b>Time:</b> {alert['timestamp']}\n"
            )

            if alert.get('details'):
                message += "\n<b>Details:</b>\n"
                for key, value in alert['details'].items():
                    message += f"• {key}: {value}\n"

            url = f"https://api.telegram.org/bot{config['bot_token']}/sendMessage"
            payload = {
                "chat_id": config['chat_id'],
                "text": message,
                "parse_mode": "HTML"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        logger.info("Telegram alert sent")
                        return True
                    else:
                        logger.error(f"Telegram API returned {resp.status}")
                        return False

        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def _is_rate_limited(self, channel_name: str) -> bool:
        """Check if channel is rate limited"""
        if channel_name not in self.rate_limits:
            return False

        last_sent = self.rate_limits[channel_name]
        cooldown = 60  # 1 minute cooldown between alerts per channel

        return (datetime.now() - last_sent).total_seconds() < cooldown

    def _update_rate_limit(self, channel_name: str):
        """Update rate limit timestamp"""
        self.rate_limits[channel_name] = datetime.now()

    def _record_notification(self, channel_name: str, alert: Dict):
        """Record notification in history"""
        self.notification_history.append({
            "channel": channel_name,
            "alert": alert,
            "sent_at": datetime.now().isoformat()
        })

        # Keep only last 1000 notifications
        if len(self.notification_history) > 1000:
            self.notification_history = self.notification_history[-1000:]


def create_default_channels() -> List[NotificationChannel]:
    """Create default notification channels from environment"""
    import os
    channels = []

    # Discord webhook (if configured)
    discord_url = os.getenv("DISCORD_WEBHOOK_URL")
    if discord_url:
        channels.append(NotificationChannel(
            name="discord_alerts",
            type="discord",
            config={"webhook_url": discord_url},
            severity_filter=["error", "critical"]
        ))

    # Slack webhook (if configured)
    slack_url = os.getenv("SLACK_WEBHOOK_URL")
    if slack_url:
        channels.append(NotificationChannel(
            name="slack_alerts",
            type="slack",
            config={"webhook_url": slack_url},
            severity_filter=["warning", "error", "critical"]
        ))

    # Email (if configured)
    smtp_server = os.getenv("SMTP_SERVER")
    if smtp_server:
        channels.append(NotificationChannel(
            name="email_alerts",
            type="email",
            config={
                "smtp_server": smtp_server,
                "smtp_port": int(os.getenv("SMTP_PORT", "587")),
                "from_email": os.getenv("ALERT_FROM_EMAIL"),
                "to_email": os.getenv("ALERT_TO_EMAIL"),
                "username": os.getenv("SMTP_USERNAME"),
                "password": os.getenv("SMTP_PASSWORD"),
                "use_tls": True
            },
            severity_filter=["critical"]
        ))

    # Telegram (if configured)
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat = os.getenv("TELEGRAM_CHAT_ID")
    if telegram_token and telegram_chat:
        channels.append(NotificationChannel(
            name="telegram_alerts",
            type="telegram",
            config={
                "bot_token": telegram_token,
                "chat_id": telegram_chat
            }
        ))

    # Generic webhook (if configured)
    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    if webhook_url:
        channels.append(NotificationChannel(
            name="webhook_alerts",
            type="webhook",
            config={
                "url": webhook_url,
                "headers": {"Authorization": os.getenv("WEBHOOK_AUTH", "")}
            }
        ))

    return channels


async def test_notifier():
    """Test alert notifier"""
    # Create notifier with test channels
    notifier = AlertNotifier()

    # Add a test webhook channel
    notifier.add_channel(NotificationChannel(
        name="test_webhook",
        type="webhook",
        config={"url": "http://localhost:8080/webhook"},
        severity_filter=["error", "critical"]
    ))

    # Test alert
    test_alert = {
        "timestamp": datetime.now().isoformat(),
        "severity": "error",
        "category": "trading",
        "message": "Test alert from monitoring system",
        "details": {
            "error_rate": 0.15,
            "failed_trades": 3,
            "whale_address": "0x1234...5678"
        }
    }

    # Send alert
    results = await notifier.send_alert(test_alert)
    print(f"Alert sent. Results: {results}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_notifier())