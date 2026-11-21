import { useState } from 'react'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card, CardBody, CardHeader } from '../../components/ui/Card'
import { ErrorMessage, PageLoader } from '../../components/ui/Feedback'
import { Input } from '../../components/ui/Form'
import { useAuth } from '../../context/AuthContext'
import { ROLE_LABEL } from '../../lib/labels'
import { useHousehold, useRenameHousehold } from './useHousehold'

/** Settings card: household name (owners can rename it) and its members with their roles. */
export function MembersSection() {
  const { user, isOwner } = useAuth()
  const { data: household, isLoading, error } = useHousehold()
  const rename = useRenameHousehold()
  const [name, setName] = useState(null) // null = not editing

  const onSave = (e) => {
    e.preventDefault()
    rename.mutate(name.trim(), { onSuccess: () => setName(null) })
  }

  return (
    <Card>
      <CardHeader title="Household" subtitle="Everyone here can see the household's shared accounts." />
      <CardBody className="space-y-4">
        <ErrorMessage error={error || rename.error} />
        {isLoading || !household ? (
          <PageLoader />
        ) : (
          <>
            {name === null ? (
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium">{household.name}</span>
                {isOwner && (
                  <Button size="sm" variant="ghost" onClick={() => setName(household.name)}>
                    Rename
                  </Button>
                )}
              </div>
            ) : (
              <form onSubmit={onSave} className="flex gap-2">
                <Input aria-label="Household name" required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} autoFocus />
                <Button type="submit" size="sm" className="h-10" loading={rename.isPending}>
                  Save
                </Button>
                <Button size="sm" variant="secondary" className="h-10" onClick={() => setName(null)}>
                  Cancel
                </Button>
              </form>
            )}

            <ul className="divide-y divide-slate-100 rounded-lg ring-1 ring-slate-200 dark:divide-slate-800 dark:ring-slate-800">
              {household.members.map((m) => (
                <li key={m.user_id} className="flex items-center justify-between gap-3 p-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">
                      {m.display_name}
                      {m.user_id === user.id && <span className="text-slate-400"> (you)</span>}
                    </p>
                    <p className="truncate text-xs text-slate-500 dark:text-slate-400">{m.email}</p>
                  </div>
                  <Badge tone={m.role === 'owner' ? 'green' : 'slate'}>{ROLE_LABEL[m.role]}</Badge>
                </li>
              ))}
            </ul>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Inviting family members as readers or contributors is coming next.
            </p>
          </>
        )}
      </CardBody>
    </Card>
  )
}
