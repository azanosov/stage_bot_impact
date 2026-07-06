from iaa_rpa_utils import get_logger

logger = get_logger(__name__)

def get_bank_reconciliation_accounts(browser) -> list[str]:
    """
    Get all available bank account names from the Bank Reconciliation report dropdown.
    """
    logger.info("Getting bank account list from Bank Reconciliation dropdown")

    try:
        browser.click_element("xpath://div[contains(@data-automationid,'Bank Account-selector-autocompleter')]//button[@aria-label='Open']")
    except Exception as e:
        logger.error(f"Failed to open bank account dropdown: {e}")
        raise

    import time
    accounts = None
    for attempt in range(10):
        accounts = browser.execute_javascript("""
            const items = document.querySelectorAll(
                "div[data-automationid='Bank Account-selector-autocompleter--list--scrollable-content'] li[aria-label]"
            );
            if (!items.length) return null;
            return Array.from(items).map(li => li.getAttribute('aria-label'));
        """)
        if accounts:
            break
        logger.info(f"Waiting for dropdown options... attempt {attempt + 1}/10")
        time.sleep(1)

    if not accounts:
        logger.error("Bank account dropdown opened but no options appeared after 10s")
        raise RuntimeError("No bank account options found in dropdown")

    logger.info(f"Found {len(accounts)} bank account(s): {accounts}")
    return accounts