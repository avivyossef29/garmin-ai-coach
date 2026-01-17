# Garmin Workout Uploader

This script uploads your marathon training workouts to Garmin Connect, which can then be synced to your Garmin watch.

## Setup

1. **Virtual environment is already created** - located in `venv/`

2. **Dependencies are installed** - `garminconnect` and all required packages

## Usage

### First Time Setup

If you're having authentication issues, test your credentials first:

```bash
source venv/bin/activate
python test_auth.py
```

This will prompt you for your email and password and test the connection.

### Running the Main Script

```bash
source venv/bin/activate
python workouts.py
```

The script will:
1. Log in to Garmin Connect (using credentials in `workouts.py`)
2. Upload all defined workouts to your Garmin account
3. Save authentication tokens to `~/.garminconnect` for future use

### Syncing to Your Watch

After the workouts are uploaded:
1. Open the Garmin Connect app on your phone
2. Sync your watch
3. The workouts will appear in your watch's workout list

## Troubleshooting

### Authentication Errors (401 Unauthorized)

If you get authentication errors:

1. **Verify credentials**: Check that your email and password in `workouts.py` are correct
2. **2FA**: If you have two-factor authentication enabled, you'll be prompted for the code during login
3. **Clear tokens**: If login keeps failing, try deleting stored tokens:
   ```bash
   rm -rf ~/.garminconnect
   ```
   Then run the script again

4. **Test authentication**: Use `test_auth.py` to verify your credentials work

### Updating Credentials

Edit the `EMAIL` and `PASSWORD` variables at the top of `workouts.py` (lines 8-9).

## Workouts

The script uploads workouts for weeks 1-7 of your marathon training plan, including:
- Aerobic runs with marathon pace intervals
- Long runs with MP blocks
- Speed intervals
- Tempo runs
- Taper workouts

All workouts are configured with your target paces for a sub-3:14 marathon.
