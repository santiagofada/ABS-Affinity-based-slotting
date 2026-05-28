WAREHOUSE SYNTHETIC DATASET
===========================

Synthetic data for warehouse slotting research. The dataset describes a
single-zone pickable warehouse (zone "A") and a coherent history of
picking and replenishment activity on top of it.

Units are inches for distances and coordinates. Timestamps are
nanosecond-precision datetimes.

Naming conventions:
    bay_id        = "A{aisle:02d}-{bay:02d}"            e.g. A14-21
    location_name = "{bay_id}-{shelf}-{bin:02d}"        e.g. A14-21-B-02
    sku           = "SKU-{n:05d}"                       e.g. SKU-00042
    merchant      = "MER-{n:03d}"                       e.g. MER-007
    user_id       = 6-digit zero-padded string          e.g. "000017"
    DOCK          = literal id of the dock / packer station

All parquet files are snappy-compressed.


FILES
=====

coordinates.parquet
-------------------
One row per bay, plus one extra row for the dock.

    bay_id       string                   Bay id, e.g. "A01-15", or "DOCK".
    zone         category(string)         Always "A"; null for DOCK.
    aisle        UInt8 (nullable)         Aisle number (1..num_aisles); null for DOCK.
    bay_number   UInt8 (nullable)         Bay index within the aisle; null for DOCK.
    side         category("odd","even")   Rack side of the aisle; null for DOCK.
                                          Odd-numbered bays sit on the lower-X side,
                                          even-numbered bays on the higher-X side.
    x            float32                  Bay center X coordinate (inches).
    y            float32                  Bay center Y coordinate (inches).


distances.parquet
-----------------
One row per unordered pair of bays (including the dock). No self-pairs,
so the file has C(n+1, 2) rows where n is the bay count. Distances are
Dijkstra shortest-path walking distances over the aisle / cross-aisle
graph (rack-internal travel is not modeled).

    bay_a        string                   Lexicographically smaller id of the pair.
    bay_b        string                   Lexicographically larger id of the pair.
    distance_in  float32                  Shortest-path walking distance, inches.


initial_stock.parquet
---------------------
One row per (bay, shelf, bin) location in the pickable zone. Empty
locations are included with null sku / merchant and 0 units. One SKU
per location; SKUs are 1:1 with non-empty locations.

    location_id           UInt32          Stable surrogate key (1..N). Referenced
                                          by picking_events and replenishment_events.
    location_name         string          Full location id, e.g. "A14-21-B-02".
    bay_id                string          Bay containing this location, e.g. "A14-21".
    sku                   string (null)   SKU stored here; null if location is empty.
    merchant_account_id   string (null)   Merchant that owns the SKU; null if empty.
    units                 UInt16          Initial stock units; 0 for empty locations.


picking_events.parquet
----------------------
One row per pick line. Picks are organized in batches of orders; within
a batch lines are sorted in snake/S-shape order by (aisle, bay_number,
shelf, bin). Each batch is executed by exactly one picker.

    batch_id              string          Batch identifier (shared across the lines
                                          of the batch).
    timestamp             datetime64[ns]  When the pick happened.
    user_id               string          Picker id (6-digit zero-padded).
    location_id           UInt32          Location picked from (joins to
                                          initial_stock.location_id).
    location_name         string          Full location id of the pick.
    bay_name              string          Bay id of the pick (e.g. "A14-21").
    sku                   string          SKU picked.
    merchant_account_id   string          Merchant of the SKU. All lines in an
                                          order share the same merchant.
    quantity              UInt16          Units picked on this line.


replenishment_events.parquet
----------------------------
One row per replenishment. Replens are reactive: a replen is inserted
just before a pick that would otherwise drive stock negative. Two cases:

    - In-place refill: stock at the SKU's current location is > 0 but
      insufficient. The SKU is refilled to capacity at the same location;
      source_location_id == target_location_id.

    - Relocation: stock at the current location is exactly 0. With
      probability relocation_probability (default 0.9) the SKU is moved
      to a random empty location and filled to capacity there;
      source_location_id != target_location_id and the old location
      becomes empty. Otherwise the replen falls back to in-place refill.

    timestamp             datetime64[ns]  When the replen happened. Equals the
                                          triggering pick's timestamp minus
                                          replen_handling_seconds.
    user_id               string          Replenisher id (6-digit zero-padded);
                                          disjoint from the picker pool.
    source_location_id    UInt32          SKU's location immediately before the
                                          replen. Equals target_location_id for
                                          in-place refills.
    target_location_id    UInt32          Location where the units land.
    location_name         string          Full location id of the target.
    sku                   string          SKU replenished.
    merchant_account_id   string          Merchant of the SKU.
    quantity              UInt16          Units delivered.


layout.html
-----------
Static HTML+SVG visualizer of the warehouse layout built from
coordinates.parquet and distances.parquet. Two select inputs pick a
pair of bays (or the dock) and the bay-to-bay walking distance is
displayed on top of the layout. Open in any modern browser.


history.html
------------
Static HTML debug visualizer of the simulated history built from
initial_stock.parquet, picking_events.parquet, and
replenishment_events.parquet. Two filterable timeline charts (one by
location, one by SKU) show stock as a step line with markers per pick
(red) and per replen (green). All event data is embedded inline as
JSON. Open in any modern browser.


JOINING THE FILES
=================

    picking_events.location_id          -> initial_stock.location_id
    replenishment_events.target_location_id  -> initial_stock.location_id
    replenishment_events.source_location_id  -> initial_stock.location_id
    picking_events.bay_name             -> coordinates.bay_id
    initial_stock.bay_id                -> coordinates.bay_id
    (bay_a, bay_b) in distances.parquet -> coordinates.bay_id (both ends)

Note that distances.parquet stores each unordered pair once, with
bay_a lexicographically smaller than bay_b. When looking up the
distance between two arbitrary bays X and Y, sort them first.
