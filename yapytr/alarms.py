"""
An Alarms class.
"""
import asyncio
from datetime import datetime

from .utils import json_preview, get_colored_logger


class Alarms:
    """
    Class to receive and print price alarms from Trade Republic.
    """

    def __init__(self, tr_api):
        """Initializes the instance.

        Args:
          tr_api: The `TradeRepublicApi` object to be used to interact with Trade Republic.
        """
        self._log = get_colored_logger(__name__)
        self._tr_api = tr_api
        self._alarms = None

    async def _alarms_loop(self):
        """
        Receive price alarms.

        Subscribe to priceAlarms from Trade Republic websocket.
        Save it in the `Alarms` object upon receipt and unsubscribe.
        """

        await self._tr_api.price_alarm_overview()

        # define flags to control the loop
        flag_price_alarms_received = 1  # 2^0

        receiption_status = 0

        desired_receiption_status = 0
        desired_receiption_status |= flag_price_alarms_received

        while receiption_status != desired_receiption_status:
            subscription_id, subscription, response = await self._tr_api.recv()

            if subscription["type"] == "priceAlarms":
                receiption_status |= flag_price_alarms_received
                self._alarms = response
            else:
                self._log.debug(
                    "unmatched subscription of type '%s':\n%s",
                    subscription["type"],
                    json_preview(response),
                )

            await self._tr_api.unsubscribe(subscription_id)

    def print_alarms(self):
        """
        Print price alarms.

        Print price alarms to the standard output stream.
        """
        print("ISIN         status created  target diff% createdAt        triggeredAT")
        for a in self._alarms:
            ts = int(a["createdAt"]) / 1000.0

            created = datetime.fromtimestamp(ts).isoformat(sep=" ", timespec="minutes")

            if a["triggeredAt"] is None:
                triggered = "-"
            else:
                ts = int(a["triggeredAt"]) / 1000.0

                triggered = datetime.fromtimestamp(ts).isoformat(
                    sep=" ", timespec="minutes"
                )

            if a["createdPrice"] == 0:
                price_difference = 0.0
            else:
                price_difference = (
                    float(a["targetPrice"]) / float(a["createdPrice"])
                ) * 100 - 100

            print(
                f"{a['instrumentId']} {a['status']} {float(a['createdPrice']):>7.2f} "
                + f"{float(a['targetPrice']):>7.2f} "
                + f"{price_difference:>5.1f} {created} {triggered}"
            )

    def get_alarms(self):
        """
        Execute the data receiving loop to receive price alarms.

        The received data can be printed with `print_alarms` method.
        """
        asyncio.get_event_loop().run_until_complete(self._alarms_loop())
