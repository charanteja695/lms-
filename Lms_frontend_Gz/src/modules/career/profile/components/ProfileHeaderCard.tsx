import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useUpdateCareerProfileMutation } from "@/modules/career/profile/api/profileApi";
import type { CareerProfile, ProfileLink } from "@/modules/career/profile/types";
import { Badge, Button, Card, DescriptionList, Field, Input, Textarea } from "@/shared/ui";

const MAX_LINKS = 6;
const MAX_ROLES = 5;

/** Headline, summary, contact, links and target roles. Name and email come from the account and are marked verified. */
export function ProfileHeaderCard({ data, editable }: { data: CareerProfile; editable: boolean }) {
  const notify = useNotify();
  const [update, { isLoading }] = useUpdateCareerProfileMutation();
  const { profile, personal } = data;
  const [editing, setEditing] = useState(false);
  const [headline, setHeadline] = useState(profile.headline ?? "");
  const [summary, setSummary] = useState(profile.summary ?? "");
  const [phone, setPhone] = useState(profile.phone ?? "");
  const [location, setLocation] = useState(profile.location ?? "");
  const [roles, setRoles] = useState(profile.target_roles.join(", "));
  const [links, setLinks] = useState<ProfileLink[]>(profile.links);

  const save = async () => {
    try {
      await update({
        headline: headline.trim() || null, summary: summary.trim() || null, phone: phone.trim() || null, location: location.trim() || null,
        target_roles: roles.split(",").map((role) => role.trim()).filter(Boolean), links: links.filter((link) => link.url.trim()),
      }).unwrap();
      notify.success("Profile saved");
      setEditing(false);
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <Card
      title={personal.name}
      description={personal.email ?? undefined}
      actions={
        editable && !editing ? <Button size="sm" variant="secondary" icon="edit" onClick={() => setEditing(true)}>Edit</Button> : personal.name_verified ? <Badge tone="green">Name verified</Badge> : null
      }
    >
      {!editing ? (
        <DescriptionList
          items={[
            { label: "Headline", value: profile.headline, span: 2 },
            { label: "Summary", value: profile.summary && <span className="whitespace-pre-wrap">{profile.summary}</span>, span: 2 },
            { label: "Phone", value: profile.phone },
            { label: "Location", value: profile.location },
            { label: "Target roles", value: profile.target_roles.join(", ") || null, span: 2 },
            { label: "Links", value: profile.links.length ? profile.links.map((link) => <a key={link.url} href={link.url} target="_blank" rel="noopener noreferrer" className="mr-3 text-brand-700 hover:underline">{link.label}</a>) : null, span: 2 },
          ]}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Headline" className="sm:col-span-2">{(props) => <Input {...props} value={headline} maxLength={160} placeholder="Final-year CSE student · Backend developer" onChange={(e) => setHeadline(e.target.value)} />}</Field>
          <Field label="Summary" className="sm:col-span-2">{(props) => <Textarea {...props} rows={3} value={summary} maxLength={1000} onChange={(e) => setSummary(e.target.value)} />}</Field>
          <Field label="Phone">{(props) => <Input {...props} value={phone} maxLength={30} onChange={(e) => setPhone(e.target.value)} />}</Field>
          <Field label="Location">{(props) => <Input {...props} value={location} maxLength={120} onChange={(e) => setLocation(e.target.value)} />}</Field>
          <Field label="Target roles" hint={`Comma separated, up to ${MAX_ROLES}.`} className="sm:col-span-2">{(props) => <Input {...props} value={roles} onChange={(e) => setRoles(e.target.value)} />}</Field>
          <div className="space-y-2 sm:col-span-2">
            <p className="text-sm font-medium text-slate-700">Links</p>
            {links.map((link, index) => (
              <div key={index} className="flex gap-2">
                <Input aria-label="Link label" className="w-40" maxLength={40} value={link.label} placeholder="GitHub" onChange={(e) => setLinks(links.map((l, i) => (i === index ? { ...l, label: e.target.value } : l)))} />
                <Input aria-label="Link URL" value={link.url} placeholder="https://" onChange={(e) => setLinks(links.map((l, i) => (i === index ? { ...l, url: e.target.value } : l)))} />
                <Button variant="ghost" size="sm" onClick={() => setLinks(links.filter((_, i) => i !== index))}>Remove</Button>
              </div>
            ))}
            {links.length < MAX_LINKS && <Button size="sm" variant="secondary" icon="plus" onClick={() => setLinks([...links, { label: "", url: "" }])}>Add link</Button>}
          </div>
          <div className="flex justify-end gap-2 sm:col-span-2">
            <Button variant="secondary" onClick={() => setEditing(false)} disabled={isLoading}>Cancel</Button>
            <Button loading={isLoading} onClick={() => void save()}>Save</Button>
          </div>
        </div>
      )}
    </Card>
  );
}
