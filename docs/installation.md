# Installation Guide

This guide walks you through setting up Carousel on your Raspberry Pi. Choose between Docker deployment (recommended) or building from source.

## Prerequisites

- **Hardware**: Raspberry Pi Zero 2W or compatible model
- **Storage**: microSD card (16GB minimum, 32GB recommended)
- **Wiring**: Complete the [wiring guide](./docs/wiring.md) before proceeding
- **Network**: Wi-Fi credentials or Ethernet connection

---

## Part 1: Prepare Your Raspberry Pi

### 1.1 Flash the Operating System

1. **Download** [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. **Insert** your microSD card into your computer
3. **Select** the following in Raspberry Pi Imager:
   - **Device**: Raspberry Pi Zero 2W (or your model)
   - **OS**: Raspberry Pi OS Lite (64-bit)
   - **Storage**: Your microSD card

### 1.2 Configure OS Settings

Click **Next** → **Edit Settings** and configure:

#### General Tab

| Setting                  | Value               | Notes                                    |
| ------------------------ | ------------------- | ---------------------------------------- |
| **Hostname**             | `carousel`          | Lowercase for consistency                |
| **Username**             | `admin`             | Default user account                     |
| **Password**             | `raspberry`         | Change after first login                 |
| **SSID**                 | Your Wi-Fi name     | Required for wireless connection         |
| **Password**             | Your Wi-Fi password | Keep secure                              |
| **Wireless LAN country** | Your country code   | e.g., `US`, `FR`, `GB`                   |
| **Timezone**             | Your timezone       | e.g., `America/New_York`, `Europe/Paris` |

#### Services Tab

- ✅ **Enable SSH**
- ✅ **Use password authentication** (or configure public key authentication)

Click **Save** → **Yes** to write the image.

### 1.3 Boot Your Raspberry Pi

1. **Eject** the microSD card safely from your computer
2. **Insert** the card into your Raspberry Pi
3. **Power on** the Pi and wait 1-2 minutes for first boot
4. **Connect via SSH** from your computer:

```bash
ssh admin@carousel.local
```

Enter the password `raspberry` when prompted.

> **Troubleshooting**: If `carousel.local` doesn't work, find your Pi's IP address from your router and use `ssh admin@<ip-address>` instead.

---

## Part 2: Install Carousel

Run the automated installation script:

```bash
curl -sSL https://raw.githubusercontent.com/MorganKryze/Carousel/main/scripts/installer.sh | bash
```

**What this script does:**

- Updates system packages
- Installs required dependencies (Git, Python, Docker, etc.)
- Configures pigpiod service for GPIO control
- Applies performance optimizations
- Clones the Carousel repository
- **Reboots the system** to apply kernel changes

> **Important**: The system will automatically reboot after installation. Reconnect via SSH after 1-2 minutes.

---

## Part 3: Deploy Carousel

After reconnecting via SSH, navigate to the project directory:

```bash
cd ~/Carousel
```

Choose your deployment method:

### Option A: Docker Deployment (Recommended)

**Advantages**: Easy updates, isolated environment, auto-updates with Watchtower

#### Initial Setup

```bash
make docker-deploy
```

This command pulls the latest images and starts the containers.

#### View Logs

```bash
# View all logs
make docker-logs

# View only Carousel logs
make docker-logs-carousel

# View only Watchtower logs (update checker)
make docker-logs-watchtower
```

#### Manage Containers

```bash
# Check status
make docker-ps

# Stop containers
make docker-down

# Restart containers
make docker-restart

# Manual update (Watchtower auto-updates daily)
make docker-update
```

---

### Option B: Build from Source

**Advantages**: Full control, development flexibility, direct hardware access

#### Step 1: Install Dependencies

```bash
make install
```

This installs Python packages and project dependencies.

#### Step 2: Build LED Matrix Library

```bash
make build
```

This compiles the `rpi-rgb-led-matrix` library and Python bindings. **This takes several minutes.**

#### Step 3: Test the Display (Optional)

```bash
make example
```

This runs a demo animation on your LED matrix. **Only run this if you've completed the wiring.**

> **Troubleshooting Display Issues:**
>
> If you encounter display problems:
>
> 1. Verify your wiring against the [wiring guide](./docs/wiring.md)
> 2. Try adding `--led-no-hardware-pulse` flag in the Makefile
> 3. Check power supply (5V 4A minimum recommended)
> 4. Ensure proper grounding connections

#### Step 4: Run Carousel

```bash
# Standard run
make run

# Development mode with debug logging
make dev

# Emulator mode (no led matrix required)
make dev-emulator
```

---

## Quick Reference Commands

### Docker Commands

```bash
make docker-deploy        # Pull images and start containers
make docker-up            # Start containers
make docker-down          # Stop containers
make docker-restart       # Restart containers
make docker-logs          # View all logs
make docker-ps            # Check container status
make docker-update        # Manual update
make docker-clean         # Remove containers and volumes
```

### Development Commands

```bash
make install              # Install dependencies
make build                # Build LED library
make setup-dev            # Install + build in one command
make run                  # Run project
make dev                  # Run with debug logging
make dev-emulator         # Run in emulator mode
make example              # Test LED matrix
make clean                # Clean build artifacts
make update               # Update repository and dependencies
make help                 # Show all available commands
```

---

## Next Steps

### Security Hardening

1. **Change default password**:

   ```bash
   passwd
   ```

2. **Update system regularly**:

   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

3. **Configure SSH key authentication** (optional but recommended):

   ```bash
   ssh-copy-id admin@carousel.local
   ```

### Configuration

- Edit settings in `~/Carousel/configs/` directory
- Logs are stored in `~/Carousel/logs/` directory
- View the [configuration guide](./docs/configuration.md) for advanced options

### Updates

- **Docker**: Watchtower automatically checks for updates every 24 hours
- **Source**: Run `make update` to pull latest changes

---

## Troubleshooting

### SSH Connection Issues

- Verify Pi is on the same network as your computer
- Try connecting via IP address instead of `carousel.local`
- Check that SSH is enabled in Raspberry Pi configuration

### Installation Script Fails

- Ensure stable internet connection
- Check available disk space: `df -h`
- Review error messages in the script output
- Report issues at [GitHub Issues](https://github.com/MorganKryze/Carousel/issues)

### Display Not Working

1. Verify wiring connections
2. Check power supply (5V 4A recommended)
3. Test with `make example` before running full project
4. Review [hardware troubleshooting guide](./docs/troubleshooting.md)

### Docker Issues

- Verify Docker is running: `sudo systemctl status docker`
- Check Docker logs: `make docker-logs`
- Restart Docker service: `sudo systemctl restart docker`

---

## Getting Help

- **Documentation**: [docs/](./docs/)
- **Issues**: [GitHub Issues](https://github.com/MorganKryze/Carousel/issues)
- **Project**: [github.com/MorganKryze/Carousel](https://github.com/MorganKryze/Carousel)
