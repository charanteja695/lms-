from lms_common.envelopes import ErrorResponse, PageContext, SortOrder, SuccessResponse


def test_success_response_has_the_fixed_envelope_shape() -> None:
    body = SuccessResponse(message="Created.").model_dump()
    assert body == {"status": "success", "code": "SUCCESS", "message": "Created."}


def test_error_response_defaults_details_to_empty_list() -> None:
    body = ErrorResponse(code="NOT_FOUND", message="Missing.").model_dump()
    assert body["details"] == [] and body["status"] == "error"


def test_page_context_computes_pages_and_has_more() -> None:
    context = PageContext.build(
        page=2, per_page=20, total=45, is_exact=True, sort_column="created_time", sort_order=SortOrder.DESC
    )
    assert context.total_pages == 3
    assert context.has_more_page is True

    last_page = PageContext.build(
        page=3, per_page=20, total=45, is_exact=True, sort_column="created_time", sort_order=SortOrder.DESC
    )
    assert last_page.has_more_page is False

    inexact = PageContext.build(
        page=500, per_page=20, total=10_000, is_exact=False, sort_column="created_time", sort_order=SortOrder.DESC
    )
    assert inexact.has_more_page is True  # an inexact final page still offers "next"
