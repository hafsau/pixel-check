"""URL policy (orchestrator/policy.py, Hafsa's idea via the council, Oct 5): Pixel-Check does not rebuild banks,
payment, crypto, government, healthcare or sign-in pages from a URL. A stated policy plus a layered check — not a
security guarantee. Written before the implementation (TDD)."""
import pytest

from orchestrator.policy import check_host, check_page, check_query


@pytest.mark.parametrize("host,category", [
    ("chase.com", "banking"), ("secure.chase.com", "banking"), ("www.bankofamerica.com", "banking"),
    ("hsbc.co.uk", "banking"), ("mybank.bank", "banking"),
    ("paypal.com", "payment"), ("www.paypal.com", "payment"), ("checkout.stripe.com", "payment"),
    ("coinbase.com", "crypto"), ("www.binance.com", "crypto"), ("metamask.io", "crypto"),
    ("irs.gov", "government"), ("www.gov.uk", "government"), ("service.gov.uk", "government"),
    ("impots.gouv.fr", "government"), ("army.mil", "government"), ("nhs.uk", "healthcare"), ("www.nhs.uk", "healthcare"),
    ("mychart.org", "healthcare"),
    ("accounts.google.com", "sign-in"), ("login.microsoftonline.com", "sign-in"), ("appleid.apple.com", "sign-in"),
    ("acme.okta.com", "sign-in"), ("acme.auth0.com", "sign-in"),
])
def test_high_risk_categories_are_refused(host, category):
    r = check_host(host)
    assert r and r["category"] == category, (host, r)


@pytest.mark.parametrize("host", [
    "paypal-secure.com", "chase-login.net", "secure-paypal.co", "paypa1.com", "chasse.com", "coinbasse.com",
    "xn--pypal-4ve.com", "chase.com.evil.io", "login.paypal.com.verify-account.net",
])
def test_lookalike_domains_are_refused(host):
    r = check_host(host)
    assert r and r["category"] == "lookalike", (host, r)


@pytest.mark.parametrize("host", ["93.184.216.34", "2606:2800:220:1::1"])
def test_raw_ip_hosts_are_refused(host):
    assert check_host(host)["category"] == "ip-address"


@pytest.mark.parametrize("host", [
    "hafsausmani.com", "vercel.com", "example.com", "databank.io", "piggybank-design.com", "foodbank.org",
    "stripes-furniture.com", "chasewalker.design", "github.com", "figma.com", "notion.com", "govdesign.studio",
])
def test_ordinary_sites_are_allowed(host):
    assert check_host(host) is None, host


@pytest.mark.parametrize("q,bad", [
    ("", False), ("ref=home&utm_source=x", False), ("token=abc", True), ("access_token=abc", True),
    ("sig=1", True), ("code=xyz", True), ("session=1", True), ("auth=1", True), ("api_key=1", True), ("key=1", True),
])
def test_links_carrying_login_tokens_are_refused(q, bad):
    assert bool(check_query(q)) is bad, q


@pytest.mark.parametrize("title,site,category", [
    ("Sign in to your Chase account", "", "banking"), ("Log in | PayPal", "PayPal", "payment"),
    ("Online Banking - Secure Login", "", "banking"), ("Coinbase - Buy & Sell Crypto", "Coinbase", "crypto"),
])
def test_page_title_and_site_name_are_a_second_signal(title, site, category):
    r = check_page(title, site)
    assert r and r["category"] == category, (title, r)


@pytest.mark.parametrize("title,site", [("Hafsa Usmani - Product Designer", ""), ("Pricing – Vercel", "Vercel"),
                                        ("Food bank volunteers", "")])
def test_ordinary_page_titles_pass(title, site):
    assert check_page(title, site) is None


def test_refusal_message_names_the_category_and_offers_the_upload_path():
    from orchestrator.policy import refusal
    m = refusal({"category": "banking"})
    assert "banking" in m and "upload your design frames" in m


def test_user_facing_messages_use_the_brand_name_without_hyphen():
    from orchestrator.policy import refusal
    assert refusal({"category": "banking"}).startswith("PixelCheck does not rebuild") and "Pixel-Check" not in refusal({"category": "x"})
