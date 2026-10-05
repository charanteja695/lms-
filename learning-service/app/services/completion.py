"""The completion rules (docs/PRODUCT.md §3.1), as a pure function of what a student has done.

  Topic complete   every required item done AND, if the topic has a test, that test passed
  Module complete  every topic complete AND, if the module has a test, that test passed
  Final eligible   every module complete

"Passed" comes from assessment-service's ``attempt.finalized`` (see app/events/consumers/assessment_events.py), so a
test only counts once its result has been released, and an invalidated pass no longer counts.
"""

from dataclasses import dataclass

from app.models.course_version_ref import CourseVersionRef


@dataclass(frozen=True, slots=True)
class Completion:
    topics: frozenset[int]  # topic ids
    modules: frozenset[int]  # module ids
    all_modules: bool  # eligible for the final test


def compute(version: CourseVersionRef, completed_items: set[int], passed_tests: set[int]) -> Completion:
    """``version`` must have its modules, topics and items loaded."""
    topics: set[int] = set()
    modules: set[int] = set()
    for module in version.modules:
        module_topics_done = True
        for topic in module.topics:
            required = {item.topic_item_id for item in topic.items if item.required}
            done = required <= completed_items and (topic.topic_test_id is None or topic.topic_test_id in passed_tests)
            if done:
                topics.add(topic.topic_id)
            module_topics_done = module_topics_done and done
        if module_topics_done and (module.module_test_id is None or module.module_test_id in passed_tests):
            modules.add(module.module_id)
    return Completion(frozenset(topics), frozenset(modules), all(module.module_id in modules for module in version.modules))
