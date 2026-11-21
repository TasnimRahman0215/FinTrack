// Form fields shared by the add and edit account dialogs.

import { Field, Select } from '../../components/ui/Form'
import { useAuth } from '../../context/AuthContext'
import { ACCOUNT_KINDS } from '../../lib/labels'
import { useHousehold } from '../settings/useHousehold'
import { ownerToValue } from './owner'

export function KindField({ value, onChange }) {
  return (
    <Field label="Type">
      {(id) => (
        <Select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
          {ACCOUNT_KINDS.map((k) => (
            <option key={k.value} value={k.value}>
              {k.label}
            </option>
          ))}
        </Select>
      )}
    </Field>
  )
}

/**
 * Household members plus "Joint". Values are strings; see owner.js for the conversion.
 * `onlyMe`: offer just "me" and "Joint" (contributors can't create accounts for other people).
 */
export function OwnerField({ value, onChange, disabled, onlyMe = false }) {
  const { user } = useAuth()
  const { data: household } = useHousehold()
  const members = (household?.members ?? []).filter((m) => !onlyMe || m.user_id === user?.id)
  return (
    <Field label="Owner" hint="Joint accounts appear in everyone's view.">
      {(id) => (
        <Select id={id} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
          {members.map((m) => (
            <option key={m.user_id} value={String(m.user_id)}>
              {m.user_id === user?.id ? `${m.display_name} (me)` : m.display_name}
            </option>
          ))}
          <option value={ownerToValue(null)}>Joint</option>
        </Select>
      )}
    </Field>
  )
}

/** Shared vs private. Joint accounts are always shared, so forms disable this for them. */
export function VisibilityField({ value, onChange, disabled }) {
  return (
    <Field label="Who can see it" hint="Private accounts only show up in the owner's own view.">
      {(id) => (
        <Select id={id} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
          <option value="shared">Shared with household</option>
          <option value="private">Private (only the owner)</option>
        </Select>
      )}
    </Field>
  )
}
