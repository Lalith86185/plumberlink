# Launch plan — one Bangalore locality first (Koramangala pilot)

Goal: **Customer → finds plumber → contacts/books → service completed → review →
platform earns revenue.** Prove it with 5–10 plumbers and 20–50 real bookings
before expanding.

## Week 1 — Supply (plumbers)

1. **Pick the locality:** Koramangala (dense apartments, high plumbing demand).
2. **Recruit 5–10 plumbers:** visit hardware/sanitary shops, ask for referrals,
   post in Koramangala Facebook/WhatsApp groups. Offer: *"Free listing, first
   10 leads free, then ₹49 per accepted lead."*
3. **Register each** at `/provider/register/` (or do it for them on your phone).
4. **Verify:** call each one, confirm they serve Koramangala, note working hours.
   **Admin → Providers → Approve.** Add starting prices (₹149 tap repair etc.).
5. **Purge demo data:** Django admin → filter `is_demo` → delete providers,
   bookings, reviews, QR codes. Keep the 15 localities + 7 services.

## Week 2 — Demand (customers)

6. **Print 20–30 QR posters:** Admin → QR codes → New → *"Koramangala — [Apartment
   name]"* → Print poster. Notice boards, laundromats, kirana stores, gyms,
   apartment WhatsApp groups (share the QR image).
7. **Poster headline does the selling:** "NEED A PLUMBER? Scan to find a nearby
   plumber." (already on the print page).
8. **Be the concierge for the first 10 bookings:** when a request comes in,
   call the plumber yourself to make sure they respond fast. Speed is the product.
9. **Close the loop:** after each completed job, send the customer the review
   link (provider dashboard shows it per booking). Reviews are your moat.

## Week 3 — Money & proof

10. **Revenue model:** keep **Lead fee ₹49** (Settings). Providers pay weekly via
    UPI against Admin → Overview → revenue ledger. First 10 leads free per
    plumber = zero-friction onboarding.
11. **Track the numbers that matter:**
    - QR scans per location (which posters work?)
    - Request → accept rate (aim >70%; chase slow plumbers)
    - Completed → review rate (aim >50%)
    - Revenue per week
12. **Kill what doesn't work:** drop localities/posters with scans but no
    bookings; double down on what converts.

## Expand only when…

- …you have **≥30 completed bookings** and **≥2 plumbers earning repeat leads**
  in Koramangala. Then clone the playbook to HSR Layout (QR codes make this
  copy-paste: one QR per apartment).
- Add Electrician category (Admin → Service categories → activate) only after
  plumbing is profitable — don't split focus.

## What NOT to build yet

Accounts for customers, OTP login, in-app payments, provider mobile app,
automatic payouts, maps/GPS. Every one of these can wait until 100+ bookings/month.
The current MVP (call + booking request + review link) is the whole pilot.
