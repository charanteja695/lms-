import { useCan } from "@/modules/user-management/common/permissions/useCan";

/** From the server's permission list (support.ask / support.agent / support.assign / support.manage / exams.manage). */
export function useSupportRights() {
  const { can, acts } = useCan();
  const isManager = can("support.manage");
  const isStaff = acts("support_queue.view", "support.agent");
  return {
    isStudent: acts("support.view", "support.ask"),
    canOpenTicket: acts("support.create", "support.ask"),
    /** Reply to and change tickets in their queue (managers and the exam team always may). */
    canAnswer: isManager || can("exams.manage") || acts("support_queue.update", "support.agent"),
    isAgent: isStaff || isManager || can("exams.manage"),
    isManager,
    isStaff,
    isHead: acts("support_queue.approve", "support.assign"),
    canWriteCanned: isManager || isStaff,
    canPromoteToFaq: isManager || acts("tutor_chats.view", "tutor.conversations.view"),
  };
}

