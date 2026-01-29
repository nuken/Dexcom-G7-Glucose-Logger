# Dexcom G7 Glucose Logger

A self-hosted Flask application that logs Dexcom G7 glucose readings to a local SQLite database.

## Features
- **Local History:** Bypasses the 24-hour limit of the Dexcom Share API by saving data locally.
- **Auto-Sync:** Background worker fetches new data every 30 minutes.
- **Mobile Friendly:** Responsive UI designed for phone screens.
- **Print Ready:** formatted for clean printing (great for doctor visits).
- **Sorting:** Sort by value or trend.

## Setup (Using Docker/Dockge)

1. Clone this repo.
2. Update the `compose.yaml` with your Dexcom credentials.
   - Set `DEXCOM_OUS=True` if you are outside the US.
3. Run `docker compose up -d`.
4. Access at `http://your-ip:5000`.

## Privacy Note
This tool stores health data in a local `glucose.db` file. Ensure you secure your server and back up this file regularly.