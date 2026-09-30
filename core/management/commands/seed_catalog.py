"""
Seed the NammaWork service catalog: localities + 8 service categories with
their bookable services. Idempotent — safe to run on every deploy.
No demo providers/bookings here (see seed_demo for clearly-marked test data).
"""
from django.core.management.base import BaseCommand

from core.models import Locality, Service, ServiceCategory

LOCALITIES = [
    "Koramangala", "HSR Layout", "BTM Layout", "JP Nagar", "Whitefield",
    "Marathahalli", "Bellandur", "Indiranagar", "Electronic City", "Hebbal",
    "Yelahanka", "Banashankari", "Jayanagar", "Malleshwaram", "Peenya",
]

# slug -> (name, icon, description, [(service name, short description), ...])
CATALOG = {
    "plumber": ("Plumber", "🔧", "Tap repair, leakage, bathroom plumbing and more.", [
        ("Tap repair", "Leaking or broken taps fixed or replaced"),
        ("Pipe leakage", "Find and fix leaking pipes"),
        ("Bathroom plumbing", "Fittings, flush tanks, sanitary work"),
        ("Drain blockage", "Kitchen / bathroom drain unclogging"),
        ("Water tank work", "Tank cleaning, inlet/outlet plumbing"),
        ("Emergency plumbing", "Urgent leaks and bursts, fast response"),
    ]),
    "electrician": ("Electrician", "⚡", "Electrical repairs, installation and wiring.", [
        ("Switch/socket repair", "Faulty switches, sockets and boards fixed"),
        ("Fan installation", "Ceiling, wall and exhaust fan fitting"),
        ("Light installation", "Tube lights, panels, chandeliers, outdoor lights"),
        ("Wiring", "New wiring and rewiring for rooms and homes"),
        ("Power issues", "Tripping, short circuits and power failure diagnosis"),
    ]),
    "carpenter": ("Carpenter", "🪚", "Furniture, doors, cabinets and other carpentry work.", [
        ("Furniture repair", "Tables, chairs, sofas and wooden furniture fixes"),
        ("Door repair", "Hinges, locks, alignment and polishing"),
        ("Cabinet work", "Kitchen cabinets, wardrobes and storage"),
        ("Bed repair", "Cots, frames and headboard fixes"),
        ("Custom carpentry", "Shelves, partitions and made-to-order woodwork"),
    ]),
    "ac-technician": ("AC Technician", "❄️", "Repair, installation and maintenance.", [
        ("AC service", "General servicing for split and window ACs"),
        ("AC repair", "Cooling issues, noise, water leakage fixes"),
        ("Installation", "Split / window AC installation and uninstallation"),
        ("Gas charging", "Refrigerant refill and leak repair"),
        ("AC cleaning", "Deep foam-jet cleaning of indoor and outdoor units"),
    ]),
    "cleaning": ("Cleaning", "🧹", "Home, bathroom, kitchen and deep cleaning.", [
        ("Home cleaning", "Full home dusting, mopping and tidying"),
        ("Bathroom cleaning", "Tiles, fittings and sanitary deep-clean"),
        ("Kitchen cleaning", "Chimney, slabs, cabinets and floor degreasing"),
        ("Deep cleaning", "Intensive whole-home cleaning, move-in/out ready"),
    ]),
    "appliance-repair": ("Appliance Repair", "🔌", "Repair services for common home appliances.", [
        ("Washing machine", "Top/front load repair and servicing"),
        ("Refrigerator", "Cooling, compressor and thermostat issues"),
        ("Microwave", "Heating, display and door problems"),
        ("Water purifier", "RO/UV service, filter and membrane replacement"),
    ]),
    "cctv-technician": ("CCTV Technician", "📹", "Installation, repair and maintenance of CCTV systems.", [
        ("CCTV installation", "New camera setup for homes and shops"),
        ("CCTV repair", "Faulty cameras, wiring and power issues"),
        ("Camera replacement", "Upgrade or replace old cameras"),
        ("DVR/NVR setup", "Recorder configuration and remote viewing"),
    ]),
    "painter": ("Painter", "🎨", "Interior, exterior and touch-up painting.", [
        ("Interior painting", "Walls, ceilings and rooms"),
        ("Exterior painting", "Building facades and outer walls"),
        ("Wall painting", "Single walls, textures and designs"),
        ("Touch-up work", "Patches, stains and small repaint jobs"),
    ]),
}


class Command(BaseCommand):
    help = "Seed localities + service catalog (idempotent)"

    def handle(self, *args, **options):
        for name in LOCALITIES:
            Locality.objects.get_or_create(name=name, defaults={"city": "Bengaluru"})
        self.stdout.write(f"Localities: {Locality.objects.count()}")

        for order, (slug, (name, icon, desc, services)) in enumerate(CATALOG.items()):
            cat, created = ServiceCategory.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "icon": icon, "description": desc,
                          "tagline": desc, "active": True, "sort_order": order + 1},
            )
            self.stdout.write(f"{'Created' if created else 'Updated'} category: {icon} {name}")
            for i, (sname, sdesc) in enumerate(services):
                Service.objects.update_or_create(
                    category=cat, name=sname,
                    defaults={"short_description": sdesc, "active": True,
                              "sort_order": i + 1},
                )
        self.stdout.write(self.style.SUCCESS(
            f"Catalog ready: {ServiceCategory.objects.count()} categories, "
            f"{Service.objects.count()} services."))
