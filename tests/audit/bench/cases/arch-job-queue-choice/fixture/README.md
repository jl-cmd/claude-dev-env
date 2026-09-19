# thumbnailer

A single-host Flask app. Uploads arrive at about 40 per minute at peak. Each
thumbnail takes 2 to 6 seconds of CPU. Today the request handler renders the
thumbnail inline and users wait.

Constraints from the owner:

- One Linux host. No new managed services. SQLite is already in use.
- A crash must not lose an accepted upload.
- Two engineers maintain this. Operational simplicity matters more than peak throughput.
