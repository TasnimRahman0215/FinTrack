// <select> values can't be null, so a joint account (owner_user_id = null) is stored as "joint"
// in forms. Used by AccountFields and the account dialogs.
const JOINT = 'joint'

/** owner_user_id <-> <select> value ("joint" = null, a joint account). */
export const ownerToValue = (ownerId) => (ownerId === null ? JOINT : String(ownerId))
export const valueToOwner = (value) => (value === JOINT ? null : Number(value))
export const isJoint = (value) => value === JOINT
