import { useState } from 'react'

import { Button } from '../../components/ui/Button'
import { ErrorMessage } from '../../components/ui/Feedback'
import { Field, Textarea } from '../../components/ui/Form'
import { useAddConnection } from './useConnections'

/**
 * Paste-a-setup-token form, shown in a dialog from ConnectionsSection. The backend claims the
 * token with SimpleFIN, stores the resulting access URL encrypted, and starts the first sync.
 */
export function AddConnectionForm({ onDone }) {
  const [token, setToken] = useState('')
  const add = useAddConnection()

  const onSubmit = (e) => {
    e.preventDefault()
    add.mutate(token.trim(), { onSuccess: onDone })
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-400">
        <li>
          In{' '}
          <a
            href="https://bridge.simplefin.org/simplefin/create"
            target="_blank"
            rel="noreferrer"
            className="font-medium text-emerald-600 hover:underline"
          >
            SimpleFIN Bridge
          </a>
          , link your banks, cards and brokerage.
        </li>
        <li>Create a new app connection and copy its <strong>setup token</strong>.</li>
        <li>Paste it below. It can only be used once.</li>
      </ol>
      <Field label="Setup token" hint="Stored encrypted on your server. FinTrack can only read data, never move money.">
        {(id) => (
          <Textarea
            id={id}
            required
            rows={3}
            spellCheck={false}
            autoComplete="off"
            className="font-mono text-xs"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
        )}
      </Field>
      <ErrorMessage error={add.error} />
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" loading={add.isPending}>
          Connect
        </Button>
      </div>
    </form>
  )
}
