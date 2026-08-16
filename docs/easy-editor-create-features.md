# Creating CAMS features with Easy Editor

Options for launching Easy Editor to **create** a weed feature, using lat/long from ArcGIS Field Maps or a web map, without also creating that feature through the ArcGIS form.

CAMS WeedLocations use **EPSG:2193 (NZTM)**. Easy Editor create needs **WGS84** lat/long in the URL.

## Why not create from the ArcGIS form

If the user starts **Add** in Field Maps or Map Viewer and then submits, ArcGIS creates a feature. If Easy Editor also creates one via the API, you get two records.

The form is still useful: after the user places a point, Arcade can read that **unsaved** geometry and build an Easy Editor URL. The problem is only **Submit** on the real CAMS layer.

`Project()` is not available in form calculated expressions. Convert NZTM in Arcade (see below).

## URL contract

Use HTTPS. Field Maps opens the device browser; Map Viewer opens a new tab.

**New feature (scratch / in-progress point):**

```text
https://dev-easy-editor.econet.nz/new?lat={lat}&lon={lon}
```

**Existing feature (already in CAMS):**

Pass `GlobalID` (or the parameter Easy Editor already uses), not lat/long.

Adjust path and query names to match the Easy Editor build. The same href works in both clients.

## Arcade: NZTM to lat/long

Form calculated expressions run in the **map** spatial reference. On the CAMS maps this is NZTM, not Web Mercator. Treating NZTM easting/northing as Web Mercator sends Wellington to the Adriatic.

```arcade
function NztmToWgs84(geometry) {
  if (IsEmpty(geometry)) {
    return [null, null]
  }

  var E = geometry.x
  var N = geometry.y

  var a = 6378137.0
  var f = 1.0 / 298.257222101
  var k0 = 0.9996
  var FE = 1600000.0
  var FN = 10000000.0
  var lon0 = 173.0 * PI / 180.0

  var e2 = 2.0 * f - f * f
  var ep2 = e2 / (1.0 - e2)
  var e1 = (1.0 - Sqrt(1.0 - e2)) / (1.0 + Sqrt(1.0 - e2))

  var M = (N - FN) / k0
  var mu = M / (a * (1.0 - e2 / 4.0 - 3.0 * Pow(e2, 2) / 64.0 - 5.0 * Pow(e2, 3) / 256.0))

  var phi1 = mu
    + (3.0 * e1 / 2.0 - 27.0 * Pow(e1, 3) / 32.0) * Sin(2.0 * mu)
    + (21.0 * Pow(e1, 2) / 16.0 - 55.0 * Pow(e1, 4) / 32.0) * Sin(4.0 * mu)
    + (151.0 * Pow(e1, 3) / 96.0) * Sin(6.0 * mu)
    + (1097.0 * Pow(e1, 4) / 512.0) * Sin(8.0 * mu)

  var T1 = Pow(Tan(phi1), 2)
  var C1 = ep2 * Pow(Cos(phi1), 2)
  var R1 = a * (1.0 - e2) / Pow(1.0 - e2 * Pow(Sin(phi1), 2), 1.5)
  var N1 = a / Sqrt(1.0 - e2 * Pow(Sin(phi1), 2))
  var D = (E - FE) / (N1 * k0)

  var phi = phi1 - (N1 * Tan(phi1) / R1) * (
    Pow(D, 2) / 2.0
    - (5.0 + 3.0 * T1 + 10.0 * C1 - 4.0 * Pow(C1, 2) - 9.0 * ep2) * Pow(D, 4) / 24.0
    + (61.0 + 90.0 * T1 + 298.0 * C1 + 45.0 * Pow(T1, 2) - 252.0 * ep2 - 3.0 * Pow(C1, 2)) * Pow(D, 6) / 720.0
  )

  var lam = lon0 + (
    D
    - (1.0 + 2.0 * T1 + C1) * Pow(D, 3) / 6.0
    + (5.0 - 2.0 * C1 + 28.0 * T1 - 3.0 * Pow(C1, 2) + 8.0 * ep2 + 24.0 * Pow(T1, 2)) * Pow(D, 5) / 120.0
  ) / Cos(phi1)

  return [Round(phi * 180.0 / PI, 6), Round(lam * 180.0 / PI, 6)]
}

var g = Geometry($feature)
if (IsEmpty(g)) { return null }

var ll = NztmToWgs84(g)
return "https://dev-easy-editor.econet.nz/new?lat=" + ll[0] + "&lon=" + ll[1]
```

A Wellington point should look like `-41.28,174.77` when you click **Run** in the Arcade editor.

If the map or scratch layer is Web Mercator (3857 / 102100), this conversion is wrong. Create trial layers in **NZGD2000 / NZTM (2193)**.

## Launch from Field Maps and the web map

Save the form **on the layer**, not only on one web map, so both clients share it.

### New feature (in-progress point)

1. Open the form in Field Maps Designer, or Map Viewer → **Configure editing** → **Forms**.
2. Add a string field (for example `LaunchURL`).
3. **Properties** → **Logic** → **Calculated value** → **+ New expression**.
4. Paste the Arcade above. Uncheck **Editable** on the field (the expression will not run if the field is editable).
5. Add an **Info** element:

```markdown
[Open Easy Editor]({expr/maps-url})
```

Use the token the editor inserts if it differs from `{expr/maps-url}`.

| Client | How the user gets the link |
| --- | --- |
| Field Maps | Collect / **+** → place point → form → tap the Info link → browser |
| Map Viewer | **Edit** → create point → same form → click the Info link → new tab |

Info elements are Markdown, not HTML. A calculated field alone shows the URL as text; the Info link is what is tappable.

This path needs **Add** on the layer the user is collecting into. Turning off Add on that layer removes Collect, so the in-progress form (and the link) never appear.

### Existing CAMS feature

Users can open Easy Editor from a **popup** (or from the form if Update is allowed) without starting Add.

1. Map Viewer → layer **Pop-ups** → **Attribute expressions**.
2. Build the Easy Editor URL (usually `GlobalID`, not lat/long).
3. Add a **Text** element: `[Open in Easy Editor]({expression/expr0})`.
4. Save the map.

The popup shows in Map Viewer and in Field Maps when the user selects an existing point.

## Options to stop ArcGIS creating the CAMS feature

### Option A — Required field the form never sets

A blank required field can block **Submit**. Easy Editor (and iNat → CAMS, and any other writer) must still set it.

**Client-side (cleaner):** put a dedicated field on the form (for example `CreatedVia`). Mark it **Required**, uncheck **Editable**, no Arcade, no default. Submit stays blocked. Easy Editor writes `EasyEditor` (or similar) when it creates the record.

**Server-side:** make the field non-nullable on the layer and leave it off the form. The user can still tap Submit; the service then rejects the edit. Easy to bypass:

- A **feature template default** fills the field and Submit succeeds.
- **Offline**, Field Maps can save a local draft and fail later on sync.

Do not reuse `SpeciesDropDown` or `LocationInfo`. Users can fill those and submit.

### Option B — Scratch layer + CAMS view with Add off (recommended for a trial)

Field Maps / Map Viewer collect onto a **scratch** layer (Add on). Easy Editor writes the real WeedLocations feature. Field users only see a **hosted view** of CAMS that cannot Add.

ArcGIS does not turn Add on or off per person on one layer. It is a capability on the **layer or view**.

- Field users get the CAMS **view** (editing off, or editing on with **Add** unchecked).
- Easy Editor creates against the **source** layer with credentials that still have Add (app/server login, or a login that can access the source).

If Easy Editor uses the **field user’s** token, and that user only has the no-Add view, create fails.

Owners and org admins with full editing control can still Add when Add is off for everyone else. Test as a normal editor.

Do **not** turn off Add on the live CAMS source item for a trial. Use a view.

### Option C — Discard the Field Maps draft

Keep Add on CAMS. User opens Easy Editor, then discards the ArcGIS draft. Easy to get wrong; they will submit.

## Trial: scratch layer and no-Add view

### 1. Scratch map and layer (Add on)

1. Field Maps Designer → **+ New map** → **Start with new layers**.
2. Name the map e.g. `CAMS scratch launch (trial)`.
3. Add a **Point** layer `ScratchLaunch`.
4. **Advanced settings** → **Set coordinate system** → **NZGD2000 / New Zealand Transverse Mercator (2193)**.
5. Create the map. Editing/Add is on by default.

### 2. Form and launch link

Follow [New feature (in-progress point)](#new-feature-in-progress-point) on `ScratchLaunch`. Until Easy Editor create exists, the same Arcade can return a Google Maps URL to prove the click path:

```arcade
return "https://www.google.com/maps?q=" + ll[0] + "," + ll[1]
```

### 3. CAMS view with Add off

1. Open the CAMS **hosted feature layer** item (owner/admin).
2. **Overview** → **Create view layer** → **View layer**.
3. Include WeedLocations (and visits if needed).
4. Title: `CAMS view no-add (trial)` → **Create**.
5. View item → **Settings** → **Feature layer (hosted, view)**:
   - turn **Enable editing** off, or
   - leave editing on and **uncheck Add**.
6. **Save**.

### 4. Same map

1. Field Maps Designer → `CAMS scratch launch (trial)`.
2. **Add layers** → `CAMS view no-add (trial)`.
3. Only `ScratchLaunch` should be editable.
4. Save the map.

### 5. Share to a test editor

1. Group e.g. `CAMS scratch trial`.
2. Add a test user who is **not** an admin and **not** the layer owner.
3. Share the scratch map, `ScratchLaunch`, and the CAMS view with that group.
4. Do not share the CAMS **source** layer with that user for the trial.

### 6. Checks (as the test user)

**Field Maps**

1. Open `CAMS scratch launch (trial)`.
2. Existing CAMS points come from the view.
3. **+** / Collect creates a point on **ScratchLaunch** only.
4. Place a Wellington point → form → link has the right lat/long.
5. Open the link.
6. Collect on the CAMS view should not be available.
7. Discard the scratch draft (or submit; it only lands on the scratch layer).

**Web map**

1. Open the same web map in Map Viewer as the test user.
2. **Edit** → add a point on ScratchLaunch → same Info link.
3. Editing/Add on CAMS features should not create a new CAMS record.

**Easy Editor (when create exists)**

Creates against the CAMS **source** with credentials that have Add. After save, the new weed appears on the CAMS view. Nothing new is required on `ScratchLaunch`.

## What belongs on which layer

| Layer | Role | Launch |
| --- | --- | --- |
| ScratchLaunch | Add on | Form Info link → Easy Editor **new** + lat/long |
| CAMS no-Add view | View / update only | Popup (or form) → Easy Editor **existing** + GlobalID |
| CAMS source | Easy Editor write | Not shared to field users in the trial |

## Caveats

- Turning off **Add** on the layer you collect into removes the in-progress form. The create link cannot live there.
- The same user cannot both be blocked from Add on CAMS and create via Easy Editor **as themselves** on that same view.
- Other CAMS writers must populate any new required/sentinel field, or those creates fail.
- Keep Field Maps reasonably current. Info elements use Markdown; HTML from Arcade is not treated as a link.
- Opening the Easy Editor link needs a network connection. The Arcade itself only uses `Geometry($feature)` and runs offline.
