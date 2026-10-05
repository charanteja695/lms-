"""Re-exports the pagination helpers shared with every LMS service; see ``lms_common.pagination``
for the implementation and its own tests. Call sites keep importing from ``app.utils.query``.
"""

from lms_common.pagination import LIKE_ESCAPE, MAX_COUNTED_RECORDS, contains_pattern, paginate

__all__ = ["LIKE_ESCAPE", "MAX_COUNTED_RECORDS", "contains_pattern", "paginate"]
