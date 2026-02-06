# Usage Guide

This guide covers how to run and interact with Carousel in different environments.

## Runtime Modes

Carousel supports two operational modes:

### Production Mode (Raspberry Pi)

Hardware-based operation using physical components:

- **Input**: GPIO hardware (tilt switch, rotary encoder)
- **Display**: LED matrix via rgbmatrix library
- **Requirements**: pigpio, gpiozero, rpi-rgb-led-matrix
- **Permissions**: Requires sudo for GPIO access

### Development Mode (Desktop)

Software simulation for testing without hardware:

- **Input**: Keyboard simulation
- **Display**: Browser-based emulator
- **Requirements**: pynput, RGBMatrixEmulator
- **Permissions**: Regular user permissions

## Keyboard Controls (Development Mode)

When running in emulator mode with `--emulator` flag:

| Key                 | Hardware Equivalent | Action                   | Timing               |
| ------------------- | ------------------- | ------------------------ | -------------------- |
| Space               | Tilt Switch         | Toggle orientation       | Instant              |
| Left Arrow          | Encoder CCW         | Rotate counter-clockwise | Per press            |
| Right Arrow         | Encoder CW          | Rotate clockwise         | Per press            |
| Down Arrow (tap)    | Encoder Button      | Single press             | Quick tap            |
| Down Arrow (2x tap) | Encoder Button      | Double press             | Within 0.3 seconds   |
| Down Arrow (hold)   | Encoder Button      | Long press               | Hold for 0.5 seconds |

## Running Carousel

### Production (Raspberry Pi)

```bash
# Standard run
make run

# Run with debug logging
make dev
```

### Development (Desktop)

```bash
# Run emulator with keyboard controls
make dev-emulator
```

The emulator will:

1. Start a web server on <http://localhost:8000>
2. Open a browser window displaying the LED matrix
3. Accept keyboard inputs for interaction

**Note**: You may see `RuntimeError: This event loop is already running` in the console. This is expected behavior with the emulator and can be safely ignored.

### Docker Deployment

```bash
# Start containers
make docker-up

# View logs
make docker-logs

# Stop containers
make docker-down

# Restart containers
make docker-restart
```

## Command Reference

### Setup Commands

Initial environment setup for different deployment targets:

```bash
make setup-prod           # Production: install dependencies + build hardware library
make setup-dev            # Development: install emulator and keyboard input
make setup-docker         # Docker: pull images and prepare environment
```

### Production Commands

Hardware-based execution on Raspberry Pi:

```bash
make install              # Install production dependencies (GPIO libraries)
make build                # Build rpi-rgb-led-matrix library (takes several minutes)
make example              # Run LED matrix demo to test wiring
make run                  # Run Carousel on hardware
make dev                  # Run with debug-level console logging
```

### Development Commands

Desktop testing without hardware:

```bash
make install-dev          # Install emulator and keyboard input libraries
make dev-emulator         # Run in browser emulator with keyboard controls
```

### Docker Commands

Container-based deployment and management:

```bash
make docker-pull          # Pull latest images from registry
make docker-up            # Start containers in detached mode
make docker-down          # Stop and remove containers
make docker-restart       # Stop and restart containers
make docker-logs          # View Carousel container logs (Ctrl+C to exit)
make docker-ps            # List running containers
make docker-deploy        # Pull images and start containers (initial deployment)
make docker-update        # Pull latest images and recreate containers
make docker-clean         # Remove containers and volumes
```

### Maintenance Commands

Cleanup and update operations:

```bash
make clean-python         # Remove Python cache and bytecode files
make clean-library        # Remove rpi-rgb-led-matrix build artifacts
make clean                # Clean both Python and library artifacts
make clean-all            # Clean everything including Docker resources
make update               # Update repository and reinstall dependencies
make help                 # Display all available commands
```

## Configuration

### Configuration Files

Carousel stores configuration in YAML format:

- **Location**: `configs/` directory
- **Active config**: Determined by generation ID tracking
- **Format**: YAML with sections for System, Apps, and Modules

### Editing Configuration

```bash
# Edit the active configuration
nano configs/example.config.yaml
```

Configuration changes for apps like Weather, Notion, or Spotify require API keys. Refer to the [configuration guide](./configuration.md) for details.

### Logs

Application logs are stored in the `logs/` directory:

```bash
# View recent logs
tail -f logs/carousel.log

# View logs with timestamps
cat logs/carousel.log
```

## Troubleshooting

### Development Mode Issues

#### Keyboard controls not responding

- Verify the browser window has focus
- Check pynput installation: `pip list | grep pynput`
- Look for "Keyboard input controller initialized" in logs

#### Emulator not displaying

- Verify RGBMatrixEmulator installation: `pip list | grep RGBMatrixEmulator`
- Check that `--emulator` flag is being used
- Review initialization logs for errors
- Ensure port 8000 is not in use: `lsof -i :8000`

#### "GPIO libraries not available" error

- This occurs when trying to run production mode on desktop
- Solution: Use `make dev-emulator` instead of `make run`

#### "pynput not installed" error

- Development dependencies not installed
- Solution: Run `make install-dev`

### Production Mode Issues

#### Display flickering or artifacts

- Verify wiring connections against [wiring guide](./wiring.md)
- Check power supply (5V 4A minimum recommended)
- Try adding `--led-no-hardware-pulse` flag in Makefile
- Ensure proper grounding connections

#### GPIO errors

- Verify pigpiod service is running: `sudo systemctl status pigpiod`
- Restart pigpiod: `sudo systemctl restart pigpiod`
- Check GPIO permissions: run with sudo

#### No response from encoder or tilt switch

- Test individual components with `make example`
- Verify GPIO pin assignments in configuration
- Check physical connections and solder joints

### Docker Issues

#### Containers won't start

- Check Docker daemon: `sudo systemctl status docker`
- Verify images pulled: `docker images | grep carousel`
- Check logs: `make docker-logs`
- Restart Docker: `sudo systemctl restart docker`

#### Cannot connect to container

- Verify container is running: `make docker-ps`
- Check if ports are already in use
- Review Docker logs for errors

#### Watchtower not updating

- Check Watchtower logs: `docker logs watchtower`
- Verify internet connectivity
- Ensure correct image tags in compose.yml

## Keyboard Shortcut Summary

Quick reference for development mode:

| Action              | Key Combination   |
| ------------------- | ----------------- |
| Horizontal/Vertical | Space             |
| Previous            | Left Arrow        |
| Next                | Right Arrow       |
| Select              | Down (tap)        |
| Quick Action        | Down (double tap) |
| Menu                | Down (hold)       |

## Best Practices

### Development Workflow

1. **Test locally first**: Use `make dev-emulator` to verify changes
2. **Use debug mode**: Add `--debug` flag for verbose logging
3. **Incremental testing**: Test each feature before moving to hardware
4. **Clean restarts**: If behavior is unexpected, restart the application

### Production Deployment

1. **Initial setup**: Use `make setup-prod` for first-time configuration
2. **Test display**: Run `make example` before full deployment
3. **Monitor logs**: Check logs regularly for errors
4. **Regular updates**: Run `make update` periodically

### Deploying with Docker

1. **Use Watchtower**: Automatic updates check daily
2. **Monitor resources**: Check container health with `make docker-ps`
3. **Backup configs**: Keep configuration files backed up
4. **Review logs**: Use `make docker-logs` to monitor application health

## Advanced Usage

### Custom Applications

To add custom applications:

1. Create a new app in `src/apps/`
2. Extend `Application` base class
3. Implement `generate(tilt_state, encoder_input)` method
4. Register in `AppManager._load_apps()`
5. Add configuration in YAML config file

Refer to existing apps like `gif_viewer.py` for examples.

### Running Multiple Instances

Docker supports running multiple isolated instances:

```bash
# Modify compose.yml to use different ports
# Run with custom compose file
docker compose -f docker/custom-compose.yml up -d
```

### Integration with External Services

Several apps support external API integration:

- **Weather**: OpenWeatherMap or AccuWeather API
- **Notion**: Notion API for todo lists
- **Spotify**: Spotify API for music control

Configure API keys in the YAML configuration file under the respective app's config section.

## Getting Help

- **Documentation**: Browse the `docs/` directory
- **Configuration**: See [configuration.md](./configuration.md)
- **Wiring**: See [wiring.md](./wiring.md)
- **Issues**: Report bugs at [GitHub Issues](https://github.com/MorganKryze/Carousel/issues)
