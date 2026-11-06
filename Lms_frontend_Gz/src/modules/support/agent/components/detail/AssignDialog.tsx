import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useAssignTicketMutation, useGetTicketAssigneesQuery } from "@/modules/support/agent/api/agentTicketsApi";
import { Button, Field, Modal, Select } from "@/shared/ui";

/** The server lists exactly who it would accept (the ticket's queue, active people). */
export function AssignDialog({ ticketId, onClose }: { ticketId: string; onClose: () => void }) {
  const notify = useNotify();
  const { data: people = [], isFetching } = useGetTicketAssigneesQuery(ticketId);
  const [assign, { isLoading }] = useAssignTicketMutation();
  const [userId, setUserId] = useState("");

  return (
    <Modal
      open
      onClose={onClose}
      title="Assign ticket"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            loading={isLoading}
            disabled={!userId}
            onClick={async () => {
              try {
                await assign({ ticketId, assigneeUserId: userId }).unwrap();
                notify.success("Ticket assigned");
                onClose();
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            Assign
          </Button>
        </>
      }
    >
      <Field label="Assign to" hint={!isFetching && people.length === 0 ? "Nobody else can take this queue's tickets right now." : undefined}>
        {(props) => (
          <Select {...props} value={userId} placeholder={isFetching ? "Loading…" : "Choose a person"} options={people.map((person) => ({ value: person.user_id, label: person.name }))} onChange={(event) => setUserId(event.target.value)} />
        )}
      </Field>
    </Modal>
  );
}
