import requests


PRODUCTION_URL = "https://svcs.ebay.com/services/search/FindingService/v1"
SANDBOX_URL = "https://svcs.sandbox.ebay.com/services/search/FindingService/v1"


class EbayAPIError(Exception):
    pass


class EbayClient:
    def __init__(self, app_id: str, env: str = "production"):
        self.app_id = app_id
        self.base_url = SANDBOX_URL if env == "sandbox" else PRODUCTION_URL

    def find_sold_items(self, seller: str, date_from: str = None, date_to: str = None) -> list[dict]:
        all_items = []
        page = 1
        total_pages = 1

        while page <= total_pages and page <= 10:
            params = self._build_params(seller, date_from, date_to, page)
            resp = requests.get(self.base_url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            result = data.get("findCompletedItemsResponse", [{}])[0]
            ack = result.get("ack", ["Failure"])[0]

            if ack not in ("Success", "Warning"):
                errors = result.get("errorMessage", [{}])[0].get("error", [{}])
                msg = errors[0].get("message", ["Unknown eBay API error"])[0] if errors else "Unknown eBay API error"
                raise EbayAPIError(msg)

            pagination = result.get("paginationOutput", [{}])[0]
            total_pages = int(pagination.get("totalPages", ["1"])[0])
            total_entries = int(pagination.get("totalEntries", ["0"])[0])

            if total_entries == 0:
                break

            items = result.get("searchResult", [{}])[0].get("item", [])
            for item in items:
                all_items.append(self._parse_item(item, seller))

            page += 1

        return all_items

    def _build_params(self, seller: str, date_from: str, date_to: str, page: int) -> dict:
        params = {
            "OPERATION-NAME": "findCompletedItems",
            "SERVICE-VERSION": "1.0.0",
            "SECURITY-APPNAME": self.app_id,
            "RESPONSE-DATA-FORMAT": "JSON",
            "itemFilter(0).name": "Seller",
            "itemFilter(0).value": seller,
            "itemFilter(1).name": "SoldItemsOnly",
            "itemFilter(1).value": "true",
            "paginationInput.entriesPerPage": "100",
            "paginationInput.pageNumber": str(page),
            "sortOrder": "EndTimeSoonest",
        }

        idx = 2
        if date_from:
            params[f"itemFilter({idx}).name"] = "EndTimeFrom"
            params[f"itemFilter({idx}).value"] = f"{date_from}T00:00:00.000Z"
            idx += 1
        if date_to:
            params[f"itemFilter({idx}).name"] = "EndTimeTo"
            params[f"itemFilter({idx}).value"] = f"{date_to}T23:59:59.000Z"

        return params

    def _parse_item(self, raw: dict, seller: str) -> dict:
        selling = raw.get("sellingStatus", [{}])[0]
        price_node = selling.get("currentPrice", [{}])[0]
        listing = raw.get("listingInfo", [{}])[0]
        condition = raw.get("condition", [{}])[0]

        return {
            "ebay_item_id": raw.get("itemId", [""])[0],
            "title": raw.get("title", [""])[0],
            "sold_price": float(price_node.get("__value__", "0") or "0"),
            "currency": price_node.get("@currencyId", "USD"),
            "sold_date": listing.get("endTime", [""])[0],
            "ebay_link": raw.get("viewItemURL", [""])[0],
            "seller": seller,
            "condition": condition.get("conditionDisplayName", [""])[0] if condition else "",
            "listing_type": listing.get("listingType", [""])[0],
        }
