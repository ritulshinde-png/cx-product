# Derived Variants & Combo SKU Requirements

> [!IMPORTANT]
> This is a new feature where we are showing visibility for different variants of products in the app as well as any combos they are a part of.

## Context

Currently we have a system on Samaan that allows us to re-package inventory from a parent SKU to a child SKU. Say we have Fresh Tomatoes as an offline only SKU where we inward inventory in bulk. In order to sell online, we then create new SKUs like Fresh Tomatoes 500 g. Then the inventory is re-packaged from Parent into Child in Tez POS after it’s in-warded into the store. While this helps with moving inventory, but because it is a manual process, we end up facing availability issues. Specifically in case of Fruits & Vegetables, we face these challenges during the morning early hours and late night, where the moved online inventory is generally exhausted.

## Requirements

### Concept & Purpose

* **Derived SKU** is a virtual SKU created by applying a unit and price conversion on an existing Parent SKU.
* It allows merchandising of the same product in smaller/larger quantities (e.g., 500g derived from 1kg).
* These SKUs are meant for online-only selling, and will not be used for offline billing (Tez POS).
* Useful for enabling flexible pack sizes in consumer-facing (CX) apps, without duplicating full SKU workflows.

### Types of Variants

We support showing visibility for different variants of products in the app:

1. **Quantity Variants**: Derived quantities from a parent SKU using a conversion factor.
   * `parent sku * conversion factor = child sku`
   * `parent sku * price multiplier = child sku price`
   * **Loose (Weight)**: E.g., Potato | 200g, 500g, 1kg, 2kg
2. **Combo Variants**: Derived quantities from 1 parent SKU or >1 parent SKU using respective conversion factors.
   * `parent sku 1 * conv factor 1 + ... + parent sku n * conv factor n = child sku`
   * `parent sku 1 * price multiplier 1 + ... + parent sku n * price multiplier n = child sku`
   * **Limitation**: Cannot input a conversion factor < 1 in child creation. A combo can only be created from original parent SKUs (child SKUs cannot be used as parents).
   * **Combo of same single sku**: E.g., Ghadi Detergent | 1kg, 1kg * 2, 1kg * 5
   * **Combo of >1 unique skus**: E.g., 1 Lays + 1 Cold Drink + 1 Biscuit = 3 combo, 1 Detergent + 1 Handwash = 2 combo
3. **Type Variants**: Type variants for items with existing packs.
   * **Quantity type variants**: Items with weight variants. E.g., Ghadi Detergent | 1kg, 2kg, 5kg, 10kg
   * **Attribute type variants**: Items with different attributes (colour, size, style, pattern, etc.). E.g., Shoes | 6, 7, 9, 13; Tshirt | red, blue, green; Pant | plain, textured, striped; Diaper | pack of 3, pack of 6, pack of 10

### Catalog & SKU Management

* **Derived SKU Creation**
  * A new Derived relation upload module will be built on Samaan to define relationships (e.g., Aata 1kg → Aata 500g).
  * Pricing of the Derived SKU will be calculated using the ratio of quantity conversion and pricing multiplier. The upload of pricing multiplier to be built separately.
  * Derived SKU will inherit attributes and shelf control logic from their catalogue — they can be modified independently.
* **Restrictions**
  * Unit changes for Parent SKUs are not allowed once a Derived SKU exists.
  * Derived SKU can only exist if a valid Parent SKU is present.
* **Channel Availability**
  * Derived SKUs will be available only on the online consumer app (CX).
  * They will not be supported or visible on Tez POS (offline billing platform).

### Inwarding

* Derived SKUs are not relevant for warehouse/store inwarding processes.
* All inwarding continues to happen against the Parent SKU only.
* To **BLOCK** any inwarding from variant (child) or combo SKU.

### Inventory & Visibility

* **Inventory Calculation**
  * No separate inventory is maintained for Derived SKUs.
  * Their available stock is calculated at runtime using the Parent SKU’s inventory and the defined conversion ratio. Round down on conversion.
  * Check in cart for inventory logic (Minimum price to be cut off). To add event for this (user, store, timestamp, event name, items).
* **Visibility Logic**
  * If a Derived SKU is inactive, it will not appear in search, listings, or any discovery surface.
  * If a Parent SKU is inactive, both Parent and Derived SKUs will be hidden from listings and search.
  * When a Derived SKU is marked active for the first time, it will become instantly visible where Parent SKU inventory is present:
    * Listings
    * Search results
    * Relevant category/product pages
* **OLP/ODP Behavior**
  * Even if marked inactive, Derived SKUs will not be removed from ODP (product detail) and OLP (offer listing) pages. **SKIP for now.**
* **Pricing**
  * Pricing is calculated at runtime using the Parent SKU’s price and the conversion (ratio x pricing multiplier) factor.
  * Pricing is store-level, based on Store × Stock ID.

### Offers

* **SKU-Level Offers**
  * Flat pricing is supported on Derived SKUs.
  * Use case: Sell 500g at ₹59 flat, instead of deriving from 1kg base price.
* **Unsupported Offers**
  * Percentage-based discounts (e.g., 20% off) are not supported on Derived SKUs.
  * Coupon offers (site-wide or SKU-specific) are not in scope for Derived SKUs.


### Returns

* Inventory to be added to Parent SKU, using conversion ratio.
* To exclude from audit, inward (listed in PRD), change selling, bulk conversion. Verify stock transaction.

## Core Challenges

For these scenarios, let's define:

* **Parent SKU:** Mango 1kg (inwarded in bulk)
* **Child SKU:** 2.5kg Mango Set (contains 4 pieces, total weight ~2.5kg)
* **Conversion Rate:** 1 unit of Child SKU consumes 2.5 kg of Parent SKU.
* **Total Initial Parent Inventory:** 50 kg of Mango 1kg at the store.

> [!WARNING]
> **Key Challenges for Developers:**
> 1.  **Fractional Inventory:** How to handle situations where the remaining parent inventory isn't a perfect multiple of the child SKU's weight, leading to "leftover" parent inventory that can't form a full child unit.
> 2.  **Picking Variations:** The actual weight of a "piece" of fruit can vary, making the exact conversion from parent to child unpredictable.
> 3.  **Concurrent Sales Channels:** Offline sales directly from the parent SKU or other child SKUs (if applicable) can impact the available parent inventory for re-packaging.
> 4.  **Real-time Availability:** Ensuring that online inventory accurately reflects what's truly available for purchase, given the dynamic nature of re-packaging, picking, and concurrent sales.
> 5.  **Order Fulfillment Logic:** What happens when an order is placed for a child SKU, but the underlying parent inventory becomes insufficient during picking or due to concurrent sales.

### I. Basic Conversion & Fractional Remainders

* **Scenario 1.1: Perfect Conversion**
  * **Initial State:** 50 kg Mango (Parent).
  * **Action:** Re-package 25 kg into Child SKU.
  * **Expected Outcome:** 10 units of 2.5kg Mango Set (Child) are created. 25 kg Mango (Parent) remain. No fractional issues.
* **Scenario 1.2: Fractional Remainder (Parent < Child Unit Weight)**
  * **Initial State:** 2.4 kg Mango (Parent). No Child SKU units available.
  * **Action:** System attempts to create a 2.5kg Mango Set (Child).
  * **Expected Outcome:** 0 units of Child SKU can be created. The 2.4 kg remains as parent inventory, effectively "locked" for creating a full child unit until more parent inventory is added. Online shows 0 availability for the Child SKU.
* **Scenario 1.3: Fractional Remainder (Parent > Child Unit Weight, but not enough for another full unit)**
  * **Initial State:** 27 kg Mango (Parent).
  * **Action:** System calculates how many 2.5kg Mango Sets can be created.
  * **Expected Outcome:** (27 kg / 2.5 kg/unit) = 10.8 units. 10 units of Child SKU are created. 2 kg Mango (Parent) remain. Online shows 10 units of Child SKU available. The 2 kg parent inventory is a remainder.

### II. Impact of Offline Sales

* **Scenario 2.1: Offline Sale of Parent SKU before Re-packaging**
  * **Initial State:** 50 kg Mango (Parent).
  * **Action:** Store sells 5 kg of Mango (Parent) directly offline (e.g., a customer buys 5 individual kgs).
  * **Subsequent Action:** System attempts to re-package the remaining parent inventory into Child SKU.
  * **Expected Outcome:** 45 kg Mango (Parent) remain. When re-packaging, fewer Child SKU units can be created (45 kg / 2.5 kg/unit = 18 units).
* **Scenario 2.2: Offline Sale of Parent SKU after Partial Re-packaging**
  * **Initial State:** 50 kg Mango (Parent).
  * **Action 1:** 25 kg of Mango (Parent) are re-packaged into 10 units of Child SKU. 25 kg Mango (Parent) remain.
  * **Action 2:** Store sells 3 kg of Mango (Parent) directly offline.
  * **Expected Outcome:** 22 kg Mango (Parent) remain. The 10 units of Child SKU remain available. Any further re-packaging will be based on the reduced parent inventory.
* **Scenario 2.3: Offline Sale of a "Child-like" Item from Parent Inventory**
  * **Initial State:** 10 kg Mango (Parent). No Child SKU units.
  * **Action:** An offline customer asks for "4 pieces of mangoes for about 2.5 kg" and the store clerk manually picks 4 pieces from the bulk parent inventory, which weigh 2.6 kg.
  * **Expected Outcome:** The 2.6 kg is deducted from the parent inventory. 7.4 kg Mango (Parent) remain. No Child SKU units are created or consumed by this offline transaction, but it impacts the remaining bulk parent inventory. This highlights the need for accurate offline POS integration or manual adjustment.

### III. Picking Variations & Inaccurate Weight Deductions

* **Scenario 3.1: Child SKU Order & Over-Picking (Weight Exceeds 2.5kg)**
  * **Initial State:** 1 unit of 2.5kg Mango Set (Child) is online. Parent inventory has 5 kg.
  * **Action:** An online order for 1 unit of Child SKU is placed. During picking, the 4 pieces picked for the set weigh 2.7 kg.
  * **Expected Outcome:** The 1 Child SKU unit is fulfilled. Instead of deducting 2.5 kg from parent inventory, 2.7 kg should be deducted. This reduces the parent inventory faster than anticipated, potentially leading to fewer future child units or fractional remainders sooner.
* **Scenario 3.2: Child SKU Order & Under-Picking (Weight Less Than 2.5kg)**
  * **Initial State:** 1 unit of 2.5kg Mango Set (Child) is online. Parent inventory has 5 kg.
  * **Action:** An online order for 1 unit of Child SKU is placed. During picking, the 4 pieces picked for the set weigh 2.3 kg.
  * **Expected Outcome:** The 1 Child SKU unit is fulfilled. Instead of deducting 2.5 kg from parent inventory, 2.3 kg should be deducted. This leaves slightly more parent inventory than anticipated. While seemingly good, inconsistencies can lead to overstating available online inventory.
* **Scenario 3.3: Fractional Parent Inventory at Picking Time**
  * **Initial State:** 2.6 kg Mango (Parent). 1 unit of 2.5kg Mango Set (Child) is online.
  * **Action:** An online order for 1 unit of Child SKU is placed. During picking, the 4 pieces are picked and weigh 2.5 kg.
  * **Expected Outcome:** The 1 Child SKU unit is fulfilled. The 2.5 kg is deducted. 0.1 kg Mango (Parent) remains. This highlights the "lost" fractional inventory that can't be used.
* **Scenario 3.4: Order for Multiple Child Units, Parent Inventory Becomes Insufficient During Picking**
  * **Initial State:** 7 kg Mango (Parent). 2 units of 2.5kg Mango Set (Child) are online (derived from 5kg, with 2kg parent remainder).
  * **Action:** An online order for 2 units of Child SKU is placed.
  * **Picking 1st Unit:** 2.5 kg is picked for the first unit. Parent inventory becomes 4.5 kg.
  * **Picking 2nd Unit:** The system expects to pick another 2.5 kg. However, due to previous offline sales, or an unexpected weight variation, or a system glitch, only 2 kg of actual mango is available in bulk, which is insufficient for the second 2.5kg set.
  * **Expected Outcome:** The first unit is fulfilled. The second unit fails to be picked. This necessitates a partial order fulfillment, cancellation of the second item, or a manual intervention by the store staff. The online inventory for the second unit was "available" but couldn't be fulfilled.

### IV. Race Conditions & Concurrency (Critical for Developers)

* **Scenario 4.1: Concurrent Online Orders Exhaust Parent Inventory**
  * **Initial State:** 6 kg Mango (Parent). 2 units of Child SKU are shown online.
  * **Action 1 (User A):** Places an order for 1 unit of Child SKU.
  * **Action 2 (User B):** Places an order for 1 unit of Child SKU almost simultaneously.
  * **System Logic:** If the system is not robust, both orders might initially be accepted because the online inventory showed 2 units.
  * **Expected Outcome:**
    * **Ideal:** Transactional locking or atomicity ensures only one order depletes the parent inventory first. The second order is then marked as out of stock or partially fulfilled.
    * **Problematic:** If not handled, both orders might consume the "available" inventory, leading to one order being unfulfillable during picking. This creates customer dissatisfaction.
* **Scenario 4.2: Online Order vs. Offline Sale Race**
  * **Initial State:** 3 kg Mango (Parent). 1 unit of Child SKU is shown online.
  * **Action 1 (Online User):** Places an order for 1 unit of Child SKU.
  * **Action 2 (Offline Customer):** Simultaneously buys 1 kg of Mango (Parent) directly from the store.
  * **Expected Outcome:**
    * If the offline sale is processed first, the parent inventory drops to 2 kg. The online order then becomes unfulfillable as it requires 2.5 kg.
    * If the online order is processed first, the parent inventory drops to 0.5 kg. The offline sale can still happen for 1 kg, leading to negative inventory or a manual refusal of the offline sale.
    * This highlights the need for real-time, synchronized inventory updates across all sales channels.

### V. Edge Cases & Error Handling

* **Scenario 5.1: Negative Parent Inventory (Due to Errors or Manual Adjustment)**
  * **Initial State:** 2 kg Mango (Parent).
  * **Action:** A manual adjustment or error causes the parent inventory to go to -1 kg (e.g., incorrect deduction).
  * **Expected Outcome:** How does the system handle this? Should re-packaging be allowed? What impact does this have on online availability of Child SKUs?
* **Scenario 5.2: Damaged Inventory / Spoilage**
  * **Initial State:** 10 kg Mango (Parent).
  * **Action:** 2 kg of Mango (Parent) are identified as spoiled and removed from inventory.
  * **Expected Outcome:** This should be accurately reflected in the parent inventory. If this 2 kg was supporting a Child SKU, the online availability of that Child SKU might need to be immediately reduced.
* **Scenario 5.3: Re-packaging a Child SKU Back to Parent (Rare, but possible)**
  * **Initial State:** 1 unit of 2.5kg Mango Set (Child) is available.
  * **Action:** Store decides to "un-package" the set and return the mangoes to bulk inventory (e.g., if the sets aren't selling).
  * **Expected Outcome:** The 2.5 kg (or actual weighed amount) should be added back to the Parent SKU inventory, and the Child SKU unit should be decremented.
* **Scenario 5.4: Incorrect Conversion Ratio or Data Entry**
  * **Initial State:** Conversion is set as 1 Child SKU = 2 kg Parent, but it should be 2.5 kg.
  * **Action:** Re-packaging occurs based on the incorrect ratio.
  * **Expected Outcome:** Inaccurate inventory levels. If 2 kg is deducted instead of 2.5 kg, the parent inventory will be over-stated, leading to future stock-outs.

## App Design & Flows

### [ADD] Button States

There are 2 states for the [ADD] button on listing and discovery surfaces:

1.  **Normal [ADD] Button**: Shown when no active variants exist or for simple items.
2.  **[ADD] Button with Options**: Shown as `[ADD | {x} OPTIONS]`.
    - `{x}` is dynamic and represents the total count of **in_stock** variants an item_code has, updating in real-time as stock levels change.
    - **Example**: If A, B, C, D are 4 variants mapped together:
        - **All in stock**: Button shows `[4 Options]`.
        - **B and C go out of stock**: Button shows `[2 Options]` (A and D only).
        - **B, C, and D go out of stock**: Only item A is available. The button state changes from `[4 Options]` to a **Normal [ADD] button**. Clicking it will directly add item A to the cart instead of opening the bottom sheet.

#### Interaction Logic (Normal [ADD])
- **Initial State**: `[ADD]`
- **Click [ADD]**: Adds 1 qty to cart. UI changes to quantity selector `[- 1 +]`.
- **Click [+]**: Adds 1 more qty (e.g., `[- 2 +]`).
- **Click [-]**:
    - If qty > 1: Reduces qty by 1.
    - If qty = 1: Removes item from cart and reverts to `[ADD]` state.

### Bottom Sheet: Variant Selection

Clicking on the `[ADD | {x} OPTIONS]` button opens a bottom sheet with two distinct zones:

#### Bottom Sheet UI Components
1. **Header**: `{Brand} + {Product Type}`
2. **Price Logic**:
    - If No Offer Price (OSP) or Selling Price (SP) → Show **MRP**
    - If No Offer Price (OSP) → Show **SP** & strike-off **MRP**
    - If Offer Price (OSP) & Locked → Show **SP** & strike-off **MRP**
    - If Offer Price (OSP) & Unlocked → Show **OSP** & strike-off **MRP**
3. **Price / Unit**:
    - Formula: price normalisation per standard unit (e.g., per 1kg or 1L).
    - **Highlighting**: The item with the lowest Price/Unit is the "Best Value" indicator. Its Price/Unit text is **Blue**, while others are **Gray**. A dedicated tag with a **Rupee Badge Icon** + text `"Best Value"` is placed immediately next to the primary text.
4. **Unit Display**: `{Unit Value} + {Unit}` (e.g., `500 g`)

#### Zone 1: Vertical Listing (Primary Variants)
Items listed one below another (top section).
- **Visibility**: Minimum 2 in-stock items, **Maximum 3 in-stock items** shown.
- **Sorting Logic**:
    1. Sort on **Best Value** (Price / Unit Ascending)
    2. If Price / Unit is same → **SP Descending**

#### Zone 2: Horizontal Listing (Explore Combos)
Items listed in a horizontal row (bottom section).
- **Header**: `{Brand} + {Product Type} + Combos`
- **Visibility**: Minimum 3 in-stock items required to render. Horizontally scrollable.
- **Rules applied to Quantity Variants**: If the selected item is a **Derived Child** (e.g., E), it cannot be part of any combos. Therefore, the Horizontal Listing **will not render** when the bottom sheet is opened for a Derived Child. It only renders when opened from the **Parent SKU** (e.g., A).
- **Sorting Logic**:
    1. Sort on **Best Value** ("% Off" Descending)
    2. If "% Off" is same → **Price / Combo SKU Ascending**
    3. If "% Off" & Price / Combo SKU same → **No Best Value SKU**

> [!NOTE]
> The logic to determine which items appear in the vertical vs. horizontal listing is based on relationship mapping, to be detailed in the next section.

## Relationship Mapping Logic

To enable dynamic visibility and selection, variants are mapped into three distinct major types based on the above definitions.

### 1. Quantity Variants (Derived)
Every quantity variant is created from **one Parent SKU** via a **conversion factor**.

- **Relationship**: Parent <-> Child. Dynamically managed; no manual grouping necessary. All parent and derived child SKUs automatically group together into the Primary Vertical list.
- **Example**: Parent A (Potato 1kg) -> Derived Children E (500g), N (200g), S (2kg).
- **Mapping Keys**:
    - `grams|str`: `560g | 560g`
    - `pack-size|str`: `400|g | 400 g`
- **Button State Triggers**: Actioning on Parent A or Child E evaluates the exact same pool. If only A or only E is in stock, the button is a normal `[ADD]`. If 2 or more from the pool (A, E, N, S) are in stock, the button becomes `[ADD | {x} Options]`.
- **Dynamic Handling**: Since these are derived, the `unit_value` should be explicitly calculated (`Parent.unit_value * conversion_factor`) and formatted using dynamic templates.
- **Figma UI Specifics (Quantity)**:
    - **Bottom Sheet Item Row**: Shows thumbnail, title (`1 kg`), Price H-Stack (`₹358` / `₹402`), and a separate `Price Breakdown Tag` below it (`₹11.6/100g`).
    - **Highlight**: Best Value tag uses Blue text and Rupee badge icon.
- **Derivation Chain Restriction**: A derived child SKU **cannot** be used as a parent to create further quantity variants or combo variants. For example, if E, N, S are derived from A: E, N, S cannot birth new SKUs. Parent A remains the only valid source for further derivations.

---

### 2. Combo Variants
Created from **quantities of 1 or more Parent SKUs** to form a single Child SKU.

- **Combo of same single SKU**:
    - **Formula**: `Parent * Quantity = Child`.
    - **Example**: Ghadi Detergent 1kg * 2 = 2kg Combo.
    - **Identification**: Flagged as `COMBO_SAME` to represent bulk/multi-pack variants of the same product.
- **Combo of >1 unique SKUs**:
    - **Formula**: `(P1 * F1) + (P2 * F2) + ... = Child`.
    - **Example**: `1 Lays + 1 Cold Drink + 1 Biscuit = 3 combo`.
    - **Identification**: Flagged as `COMBO_DIFF`. Logic should allow for listing individual components within the combo or treating the combo as a single "style" or "bundle" variant.
- **Limitations**:
    - Conversion factor must be >= 1.
    - Combos can only be created from original parent SKUs (no child SKUs as parents).

#### Combo-Specific UI & Behaviors
- **Button State Triggers**: Actioning on a combo (e.g., C1) pulls a pool of ALL combos that share at least one component with C1. If only C1 is in stock, it shows `[ADD]`. If 2 or more from this shared-component pool are in stock, it shows `[ADD | {x} Options]`.
- **Bottom Sheet UI Details**:
    - **Header**: `"Explore Combos"`
    - **Price Logic**: If No Selling Price (SP) → Show **MRP**. (Note: Offer Price/OSP is currently **not allowed** on Combo variants).
    - **Unit Display**:
        - If combo contains **>1 unique SKUs**: `{Count Distinct SKU} + Combo` (e.g., `3 Combo`). The PDP title uses a `+` separator for ingredients: `A 1kg + B 200ml`. The unit tag is `| 3 Combo`.
        - If combo contains **only 1 unique SKU**: `{unit_value} {unit} * {qty}` (e.g., `500g * 3` or `10ml * 2`).
    - **Vertical Listing (Primary)**: Shows all in-stock related combos.
    - **Horizontal Listing (Secondary)**: **Will NOT render** for Combo Variants. Horizontal listing is strictly for Standalone -> Combo exploration, never Combo -> Combo.
- **Figma UI Specifics (Combo)**:
    - **Horizontal Widget Details**: Item title (full component names joined by `+`), followed by H-stack containing Price + `"|"` + Unit tag. No Price Breakdown Tag is shown for combos.
- **Sorting Logic (Vertical Listing)**:
    1. Sort on **Best Value** ("% Off" Descending)
    2. If "% Off" is same → **Price / Combo SKU Ascending**
    3. If "% Off" & Price / Combo SKU same → **No Best Value SKU**
- **Combo PDP specific requirements**:
    - Display the combined variant image.
    - Display a **"Combo Items"** section below the variants list, detailing all individual components.
    - Each component row must show its item image, name, and individual SP/MRP.
    - Each row is **clickable**, routing the user to the respective standalone PDP of that component.

#### Shared Real-Time Inventory & Cart Limits (Combos)
Combos consume inventory directly from their base components in real-time. Adding cross-combos draws from the exact same physical stock pool.
- **The Math**: Combo C1 requires components A, B, C. Combo C2 requires components B, D.
- **The Conflict**: If the store has 1000 units of A, C, D, but only **5 units of B**.
- **The Live Constraint**: A user adds 4 quantities of C1 (consuming 4 units of B). They then add 1 quantity of C2 (consuming 1 further unit of B). The total available pool of B is now 0.
- **Blocked Addition**: The user has exhausted component B. They cannot add any more C1 or C2. Attempting to click `[+]` on either will **block the addition** and trigger a snackbar stating: `"No more stock left to add"`.
- *Note:* The user can navigate elsewhere and successfully add Standalone A, C, or D to the cart, but anything requiring B is locked.

---

### 3. Type Variants (Existing Packs)
These are independent SKUs with existing packs grouped together. Currently, they use a CSV upload:
`group_seed | item_code | key_1 | value_1 | display_name_1`

- **group_seed**: Common identifier for the variant group.
- **Subtypes**:
    - **Quantity type variants**: Items with weight variants (e.g., Ghadi Detergent 1kg, 2kg, 5kg).
    - **Attribute type variants**: Items with attributes like colour, size, style (e.g., Shoes 6, 7, 9).
- **Mapping Restrictions**: Manual mapping of these Standalone SKUs is strictly guarded. Items mapped together MUST have the exact same:
    1. `product_type`
    2. `brand`

#### Allowed Mapping Keys (`key_1`)
The UI handles presentation based on the specific template key used. The following keys are recognized:
- `color|hexcode`: e.g., Phone, Headphone, Clothes, Bottles, Toys
- `style|str`: e.g., Bags (Spiderman - Queen - Marvel)
- `pattern-type|str`: e.g., Clothes (Plain - Printed)
- `grams|str`: e.g., Apple (500g - 200g - 1kg)
- `size|str`: e.g., Shoes (M - L - XL), Clothes (M - L - XL), Bottles (1L - 2L - 500ml)
- `size|int`: e.g., Shoes (6 - 7 - 8), Clothes (36 - 38 - 40)
- `pack-size|str`: e.g., Egg (3Pc - 1Pc), Diaper (6Pc - 12Pc - 24Pc)

#### Type-Variant Specific UI & Behaviors
- **Button State Triggers (on ATC of A)**:
    - **Vertical Listing**: Shown if there are `>1 mapped` AND `>1 in-stock` variants in the group.
    - **Horizontal Listing**: Shown if there are `>2 mapped` AND `>2 in-stock` combos containing A. Hidden if `<3 mapped` OR `<3 in-stock`.
- **Figma UI Specifics (Type Variant)**:
    - **Variant Selection Widget (Bottom Sheet)**: Instead of a generic row, categorical types display as a `PDP/Text Selection Item` grid (e.g., rectangular chips for `500g`, `1 kg`, `2 kg`).
    - Chips contain the unit text in the center and the SP/MRP inside the chip box. 
    - The Best Value Star/Rupee badge floats above the chip or sits immediately adjacent.
- **Sorting Logic (Vertical Listing)**:
    1. Sort on **Best Value** (Price / Unit Ascending)
    2. If Price / Unit is same → **Selling Price Descending**
    3. If Price / Unit & Selling Price same → **No Best Value SKU**
- **Sorting Logic (Horizontal Listing)**:
    1. Sort on **Best Value** ("% Off" Descending)
    2. If "% Off" is same → **Price / Combo SKU Ascending**
    3. If "% Off" & Price / Combo SKU same → **No Best Value SKU**

#### 💡 Improvement: Dynamic Templates for Unit-Based Keys
For keys that rely on physical measurements (e.g., `grams|str`, `pack-size|str`, `volume|str`), we can automate the display name:
- **Source of Truth**: Fetch `unit` and `unit_value` from the `smpcm_product` table.
- **Dynamic Logic**:
    - `grams|str` -> Template: `{unit_value}{unit}` (e.g., `500` + `g` = `500g`)
    - `pack-size|str` -> Template: `{unit_value} {unit}` (e.g., `1` + `kg` = `1 kg`)
- **Auto-Sync**: Any change in the `smpcm_product` table for these specific item codes triggers an automatic update to the variant's display string.

> [!NOTE]
> **Manual Entry Required**: Categorical keys like `color|hexcode`, `size|str` (e.g., M | Medium), `style|str`, or `pattern-type|str` will continue to require manual entry via CSV as they do not map directly to `unit_value` fields.

---

## Data Maintenance & Feeding Strategy

### A. Unified Variant Metadata Model
Instead of type-specific tables, use a central `ProductVariantMapping` model with an `origin_type` ENUM:
- `QUANTITY_DERIVED` (Type 1)
- `COMBO_SAME` (Type 2a)
- `COMBO_DIFF` (Type 2b)
- `TYPE_VARIANT_FIXED` (Type 3)

### B. Intelligent Auto-Grooming
1. **Type Variant Creator**: When a user uploads a `group_seed`, the system auto-fetches `unit`/`unit_value` for all `item_codes` and suggests the `key_1` and `display_name`.
2. **Quantity Variant Listener**: When a new Derived SKU is created in Samaan (Parent-Child relationship), the system automatically adds it to the variant group of the Parent.
3. **Combo Registry**: All combo creations should automatically register their parents in the mapping table to enable "Explore Combos" visibility on the Parent PDP.

## Rendering & Visibility Logic

The app uses a gatekeeper logic to determine when to show options and how to render the bottom sheet zones.

### 1. Section Definitions

- **Primary Section (Vertical Listing)**:
    - **Source**: All items sharing the same `group_seed` as the selected item.
    - **Role**: Primary variants (Size, Color, etc.).
    - **Display Limits**: Minimum 2 in-stock items, **Maximum 3 in-stock items** shown.
- **Secondary Section (Horizontal Listing)**:
    - **Source**: All combos that contain the selected item as a parent component.
    - **Role**: "Explore Combos" or bundle offers.
    - **Display Limits**: Minimum 3 in-stock items required to render. The section is horizontally scrollable if there are more than 3 items.

### 2. Visibility & Trigger Rules (The Gatekeeper)

The display of the `[ADD | {x} OPTIONS]` button and the Bottom Sheet is governed by the state of the **Primary Section**.

| Condition | Primary Section (In-Stock) | Secondary Section (In-Stock) | Result |
| :--- | :--- | :--- | :--- |
| **P1** | <= 1 item | Any count | **Normal [ADD] Button**. No Bottom Sheet. |
| **P2** | > 1 items | < 3 items | **[ADD | {x} OPTIONS]** Button. Bottom Sheet shows **Vertical Listing only**. |
| **P3** | > 1 items | >= 3 items | **[ADD | {x} OPTIONS]** Button. Bottom Sheet shows **Vertical + Horizontal Listing**. |

### 3. Shared Real-Time Inventory & Cart Limits
Because Quantity Variants and Combo Variants draw from the exact same physical warehouse inventory, adding items to the cart across different variants consumes from a **single pooled budget**.

- **The Math**: If Store has 10kg total of A (1kg units). This means 10 physical units of A exist. Simultaneously, this means 20 available units of E (0.5kg) exist. The total pooled mass is 10kg.
- **The Live Constraint (Add To Cart Action)**: If pooled quantity for requested variants < total available qty, allow the addition. If pooled quantity > total available qty, block the ATC action and show a bottom snackbar stating: `"No more stock left to add"`.
- **Live State Recalculation (Cart Page Auto-Reduction)**: This shared limit applies across all active users.
    - Example: If Customer X has added all available stock of A to their cart, but Customer Y buys 1 quantity of A.
    - Customer X's cart is automatically evaluated and the quantity of A is reduced by 1.
    - An error state message is appended to the exact item in the cart: `"1 qty removed due to low availability"`.
    - If the item's available pool hits 0, it drops to a disabled state with an `"Out of stock"` label.

### 4. Critical Business Rules

1.  **Primary is Mandatory**: The bottom sheet **will NOT open** if the Primary section has 1 or fewer in-stock variants, even if multiple combos exist. It needs **at least 2 items** in stock to show.
2.  **Secondary Threshold**: The Secondary section (Horizontal Listing) requires a minimum of **3 in-stock items** to render. It needs **at least 3 items** in stock to show. If count < 3, the section is suppressed entirely.
3.  **Standalone Secondary Prohibited**: The Secondary section can never trigger the Bottom Sheet or the Options button on its own. It is always a "plus-one" to a valid Primary section.
4.  **Fallback Mechanism**: If at any point the number of in-stock items in the Primary section drops to 1, the item reverts to the normal `[ADD]` state immediately on the listing page.

## Key Takeaways for Developers

1.  **Single Source of Truth:** The parent SKU inventory (in kg) should be the ultimate source of truth for all calculations. Child SKU availability should always be derived from the parent.
2.  **Atomic Operations:** Re-packaging and sales (online/offline) must be atomic operations that update the parent inventory. This prevents race conditions.
3.  **Real-time Updates:** Inventory updates must be real-time and propagate quickly across all sales channels to prevent overselling.
4.  **Tolerance for Fractions:** The system needs to intelligently handle fractional parent inventory. This might mean:
    * Rounding down to the nearest whole unit for online display.
    * Displaying "0 units available" if the remaining parent is less than a child unit.
    * Flagging small remainders for manual reconciliation.
5.  **Actual Weight Tracking:** For picking, consider implementing actual weight capture at the POS/picking station to accurately deduct from parent inventory. If not feasible, an estimated average weight for the Child SKU should be used, with a clear understanding of potential discrepancies.
6.  **Backorder/Partial Fulfillment Logic:** How should the system respond when an order can't be fully fulfilled due to sudden inventory changes during picking? (Addressed in Post-Order Partial Cancellation).
7.  **Auditing and Reconciliation:** Tools for store staff to easily audit current inventory, identify discrepancies, and reconcile actual vs. system inventory.
8.  **User Interface Considerations:** Clearly communicate to users (both store staff and online customers) the implications of variable weights and potential partial availability. For example, "Approximately X units available."

## Post-Order Partial Cancellation (Combo Breakdown)

If a user orders a Combo Variant, but one or more of its child SKUs get cancelled post-order (due to actual store unavailability, damage, expiration, etc.), the combo undergoes a **partial cancellation breakdown**.

- **Breakdown Logic**: Post-order, the combo breaks down into its individual component SKUs. Pricing for each component is calculated strictly as per its defined `price multiplier` in the combo setup.
- **Example Scenario**:
    - **Order**: Combo C1 (contains A, B, C).
    - **Event**: Component B goes Out of Stock during store picking and is cancelled.
    - **Order Details View (CX App)**:
        - The original Combo C1 is no longer shown as a single bundled item.
        - The active item list will now independently show **A** and **C** as individual products.
        - The Updated/Cancelled items section will show **B** as the cancelled product.
    - **Financial Sync**: The prices for A, B, and C are calculated individually using the price multiplier.
        - **COD Orders**: The customer pays the reduced, re-calculated amount (Total - Cancelled B).
        - **Prepaid Orders**: The customer is refunded the exact calculated amount of the cancelled item B.

---

## Conclusion
By considering these exhaustive scenarios, developers can design a robust and reliable inventory management system that addresses the complexities of re-packaging, fractional quantities, and multi-channel sales.
