"""The RPA failure taxonomy (Ingredion's error analysis) reproduced from the raw messages."""

from __future__ import annotations

import pytest

from factory.rules.reason_codes import CATALOGUE
from order_intake_agent.models import ErrorCategory
from order_intake_agent.rpa_errors import (
    PROFILES,
    TEXT_DERIVED,
    Addressed,
    RPAErrorType,
    classify_rpa_message,
    normalise_message,
)

# One real message shape per category (numbers and names altered), as exported from the case field.
MESSAGES = {
    RPAErrorType.SUM_OF_LINE_TOTAL: "PO_4500.pdf ---&gt; Failed ---&gt; The following validation fails while processing the data Sum of Line Total : 1200.0 does not equals to Grand Total : 1250.0&lt;br&gt;",
    RPAErrorType.PO_ALREADY_CREATED: "0000190151-R496.PDF ---&gt; Failed ---&gt; This purchase order number 190151-R496 has been already processed by BOT.&lt;br&gt;",
    RPAErrorType.GRAND_TOTAL_NOT_NUMERIC: "PO 1.pdf ---&gt; Failed ---&gt; The following validation fails while processing the data Grand Total is not numeric : anyshipmentexceeding10%overthePOorderedquantityrequireswrittenapprovalfromthe&lt;br&gt;",
    RPAErrorType.ZERO_QUANTITY: "PO-1264577.pdf ---&gt; Failed ---&gt; Zero Quantity Error for Customer : Batory Foods; Customer Material : 20412; Ordered Quantity: 2000; SAP Bag Weight : 2204; SAP Pallet : 1&lt;br&gt;",
    RPAErrorType.NO_LINE_ITEMS: "PO 112810.pdf ---&gt; Failed ---&gt; No line level Items exists with Model ID 9c3-4a-1e. Please check the line level item labelling and train the PDF accordingly.&lt;br&gt;",
    RPAErrorType.CUSTOMER_MATERIAL_NOT_AVAILABLE: "K2011.pdf ---&gt; Failed ---&gt; The following customer mapping material details are not available ID : 1216; Customer : Essex; Customer Material : 77; CustomerAddress : 1 Callahan; CustomerCity : SAYREVILLE&lt;br&gt;",
    RPAErrorType.MULTIPLE_PROFILES: "PO.pdf ---&gt; Failed ---&gt; The following customer mapping material has multiple profiles available Customer : ICI FOODS; Customer Material : 5; CustomerAddress : 1 Crypton Drive; CustomerCity : Kings Mountain&lt;br&gt;",
    RPAErrorType.MAX_LOAD: "PO#2095214.pdf ---&gt; Failed ---&gt; The following customer material exists MAX Load ID : 121465; Customer : Ken's Foods, Inc; Customer Material : 9; CustomerAddress : 1 D'ANGELO DRIVE; CustomerCity : MARLBOROUGH; Quantity : 48000&lt;br&gt;",
    RPAErrorType.MISSING_LABEL_NAMES: "PO.pdf ---&gt; Failed ---&gt; The following label name(s) are not present. Please check these labelling and train the PDF accordingly in Form recognizer. 1. Grand Total The following label name(s) values are not extracted successfully 1. Grand Total&lt;br&gt;",
    RPAErrorType.LABEL_VALUES_NOT_EXTRACTED: "PO.pdf ---&gt; Failed ---&gt; The following label name(s) values are not extracted successfully 1. SAP Material 2. Unit Price &lt;br&gt;",
    RPAErrorType.DELIVERY_DATE_FORMAT: "PO.pdf ---&gt; Failed ---&gt; The following validation fails while processing the data Delivery date format conversion issue : 4 Aug 26 at 10:00 hours&lt;br&gt;",
    RPAErrorType.UNIT_PRICE_NOT_NUMERIC: "PO.pdf ---&gt; Failed ---&gt; The following validation fails while processing the data 1. Unit Price is not a Numeric value: LB&lt;br&gt;",
    RPAErrorType.SALES_ORDER_NOT_GENERATED: "PO.pdf ---&gt; Failed ---&gt; SalesOrderNumber could not be generated due to:{&quot;BAPIRET2&quot;:[{&quot;TYPE&quot;:&quot;S&quot;,&quot;MESSAGE&quot;:&quot;SALES_HEADER_IN has been processed successfully&quot;}]}&lt;br&gt;",
    RPAErrorType.NO_MODEL_ID: "No Model ID exists for Account Name : SENSORY EFFECTS POWDER SYSTEMS Account Number : 1 Web Email : buyer@example.com&lt;br&gt;",
    RPAErrorType.MISCELLANEOUS: "K20111544 Ing.pdf ---&gt; Failed ---&gt; Error in logic app",
}


def test_customer_mapping_missing_is_not_derivable_from_the_text():
    # Ingredion assigned these 29 cases from the mapping database; the message itself reports an
    # extraction failure, which is what the classifier returns.
    msg = "PO-1264629.pdf ---&gt; Failed ---&gt; The following validation fails while processing the data No line level Items are not extracted properly with Model ID d4d0b45f-36b0. Please check the line level item labelling and train the PDF accordingly&lt;br&gt;"
    assert classify_rpa_message(msg).error_type is RPAErrorType.NO_LINE_ITEMS
    assert RPAErrorType.CUSTOMER_MAPPING_MISSING not in TEXT_DERIVED
    assert PROFILES[RPAErrorType.CUSTOMER_MAPPING_MISSING].addressed is Addressed.BY_DESIGN


@pytest.mark.parametrize("expected,message", list(MESSAGES.items()), ids=[t.name for t in MESSAGES])
def test_each_rpa_category_is_recognised(expected, message):
    err = classify_rpa_message(message)
    assert err.error_type is expected
    assert err.profile.reason_code in CATALOGUE, err.profile.reason_code


def test_every_profile_points_at_a_catalogue_code_and_a_step():
    assert set(PROFILES) == set(RPAErrorType)
    for profile in PROFILES.values():
        assert profile.reason_code in CATALOGUE
        assert profile.agent_step.startswith("A")
        assert profile.how


def test_ingredions_precedence_for_concatenated_messages():
    # Ingredion files a message that mentions a label list with "Delivery Date" under Delivery Date Format,
    # and one that ends in "multiple profiles" under Multiple Profiles, whatever came first in the text;
    # for everything else the failure that appears first in the text wins.
    labels_then_price = "PO.pdf ---&gt; Failed ---&gt; The following label name(s) are not present. 1. Unit Price 2. SAP Material The following validation fails while processing the data 1. Unit Price is not a Numeric value: &lt;br&gt;"
    assert classify_rpa_message(labels_then_price).error_type is RPAErrorType.MISSING_LABEL_NAMES
    labels_with_date = "PO.pdf ---&gt; Failed ---&gt; The following label name(s) values are not extracted successfully 1. SAP Material 2. Delivery Date &lt;br&gt;"
    assert classify_rpa_message(labels_with_date).error_type is RPAErrorType.DELIVERY_DATE_FORMAT
    date_then_profiles = "PurchaseOrder.PDF ---&gt; Failed ---&gt; The following validation fails while processing the data Delivery date format conversion issue : 13 Aug 2026 at 23:59 hoursThe following customer mapping material has multiple profiles available Customer : Bill to address&lt;br&gt;"
    err = classify_rpa_message(date_then_profiles)
    assert err.error_type is RPAErrorType.MULTIPLE_PROFILES
    assert err.also == (RPAErrorType.DELIVERY_DATE_FORMAT,)


def test_concatenated_runs_take_the_first_failure_and_keep_the_rest():
    msg = (
        "PO.pdf ---&gt; Failed ---&gt; The following customer mapping material details are not available ID : 1; Customer : Batory Foods; "
        "Customer Material : 2; CustomerAddress : 1 W Design Rd; CustomerCity : WilmingtonZero Quantity Error for Customer : Batory Foods; "
        "Customer Material : 2; Ordered Quantity: 1; SAP Bag Weight : 50; SAP Pallet : 1&lt;br&gt;"
    )
    err = classify_rpa_message(msg)
    assert err.error_type is RPAErrorType.CUSTOMER_MATERIAL_NOT_AVAILABLE
    assert err.also == (RPAErrorType.ZERO_QUANTITY,)
    assert err.attachment == "PO.pdf"


def test_terms_attachment_run_after_a_successful_po_is_flagged_as_multi_attachment():
    msg = (
        "Success ---&gt; 8084299 &lt;br&gt;PENNANT INGREDIENTS -- TERMS AND CONDITIONS.PDF ---&gt; Failed ---&gt; "
        "No line level Items exists with Model ID 1. Please check the line level item labelling and train the PDF accordingly.&lt;br&gt;"
    )
    err = classify_rpa_message(msg)
    assert err.error_type is RPAErrorType.NO_LINE_ITEMS
    assert err.multi_attachment is True


def test_coarse_groups_match_the_sow_split():
    coarse = {t: PROFILES[t].coarse for t in RPAErrorType}
    assert coarse[RPAErrorType.SUM_OF_LINE_TOTAL] is ErrorCategory.EXTRACTION
    assert coarse[RPAErrorType.CUSTOMER_MATERIAL_NOT_AVAILABLE] is ErrorCategory.MAPPING_DATA
    assert coarse[RPAErrorType.PO_ALREADY_CREATED] is ErrorCategory.SAP
    assert coarse[RPAErrorType.MAX_LOAD] is ErrorCategory.MAX_LOAD
    assert sum(1 for t in RPAErrorType if coarse[t] is ErrorCategory.EXTRACTION) == 8
    assert sum(1 for t in RPAErrorType if coarse[t] is ErrorCategory.MAPPING_DATA) == 4
    assert sum(1 for t in RPAErrorType if coarse[t] is ErrorCategory.SAP) == 2


def test_duplicates_are_routing_not_creation():
    assert PROFILES[RPAErrorType.PO_ALREADY_CREATED].addressed is Addressed.ROUTING
    assert PROFILES[RPAErrorType.PO_ALREADY_CREATED].reason_code == "EMAIL.DUPLICATE_SUBMISSION"


def test_normalise_strips_html():
    assert normalise_message("a ---&gt; b&lt;br&gt;c") == "a ---> b\nc"
