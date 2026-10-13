"""How long each order waits from arrival until its batch is released.

The data has no order arrival time, so the rule is explicit:

- Orders arrive in FIFO order and evenly, ``batch_size`` per slot (a slot is
  the time between two consecutive batches).
- A pool of ``window * batch_size`` orders is complete when its last order
  arrives. From then on its batches leave one per slot, the same pace as FIFO,
  the batch holding the oldest order first.

So for the order in arrival position ``r`` (from 0), in pool ``p``, whose batch
leaves in turn ``t`` (0 = first)::

    wait = (r_max(p) + 1) / batch_size + t - r / batch_size      [slots]

With ``window = 1`` (FIFO) the wait goes from ``1 / batch_size`` to 1 slot.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import orders_by_arrival


def order_waits(picking: pd.DataFrame, window: int, batch_size: int = 25) -> pd.Series:
    """Wait of every order, in slots, indexed by order id in arrival order."""
    order = orders_by_arrival(picking)
    position = pd.Series(np.arange(len(order)), index=order)                       # r
    batch = picking.drop_duplicates("order_id").set_index("order_id")["batch_id"].reindex(order)
    pool = position // (window * batch_size)                                         # p
    complete = (position.groupby(pool).transform("max") + 1) / batch_size          # pool complete
    oldest = position.groupby(batch).min()                                           # oldest order per batch
    turn = oldest.groupby(pool.groupby(batch).first()).rank(method="first") - 1     # t
    return complete + batch.map(turn) - position / batch_size
