# Color definitions for logging
GREEN := $(shell tput setaf 2)
BLUE := $(shell tput setaf 4)
RED := $(shell tput setaf 1)
ORANGE := $(shell tput setaf 3)
RESET := $(shell tput sgr0)

# Docker compose file location
COMPOSE_FILE := docker/compose.yml

# ===== Development targets =====
.PHONY: install
install:
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Installing project python dependencies...$(RESET)"
	@sudo pip install --break-system-packages --no-cache-dir --ignore-installed -e . || \
		{ echo "[$(RED)  ERROR  $(RESET)] $(RED)Failed to install project dependencies. Please check the logs for error.$(RESET)"; exit 1; }
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Project dependencies installed successfully.$(RESET)"

.PHONY: build
build:
	@echo "[$(ORANGE)  WARN   $(RESET)] $(ORANGE)Building the 'rpi-rgb-led-matrix' will take several minutes. Please be patient. Warnings can be safely ignored.$(RESET)"
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Building 'rpi-rgb-led-matrix' library api examples...$(RESET)"
	@make -C ./rpi-rgb-led-matrix/examples-api-use
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Building 'rpi-rgb-led-matrix' Python bindings...$(RESET)"
	@make -C ./rpi-rgb-led-matrix build-python
	@sudo make -C ./rpi-rgb-led-matrix install-python
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Project built successfully.$(RESET)"
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)If you did the wiring, you may test the library: run 'make example' or 'make run' to run the entire project.$(RESET)"

.PHONY: example
example:
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Running example demo...$(RESET)"
	@D=""; \
		while [ -z "$$D" ]; do \
			TMP=$$(shuf -i 0-11 -n 1); \
			case "$$TMP" in 1|2|3) ;; *) D=$$TMP ;; esac; \
		done; \
		sudo ./rpi-rgb-led-matrix/examples-api-use/demo -D $$D --led-rows=32 --led-cols=64 || \
			{ echo "[$(RED)  ERROR  $(RESET)] $(RED)Failed to run example demo. Please check the logs for error.$(RESET)"; exit 1; }
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Example demo completed.$(RESET)"

.PHONY: run
run:
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Running project...$(RESET)"
	@cd $(shell pwd) && sudo python src
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Project stopped.$(RESET)"

.PHONY: dev
dev:
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Running project with debug-level console logging...$(RESET)"
	@cd $(shell pwd) && sudo python src --debug
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Project running with debug logging.$(RESET)"

.PHONY: dev-emulator
dev-emulator:
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Running project with debug-level console logging in emulator mode...$(RESET)"
	@cd $(shell pwd) && sudo python src --debug --emulator
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Project running in emulator mode with debug logging.$(RESET)"

# ===== Docker deployment targets =====
.PHONY: docker-pull
docker-pull:
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Pulling latest Docker images...$(RESET)"
	@docker compose -f $(COMPOSE_FILE) pull || \
		{ echo "[$(RED)  ERROR  $(RESET)] $(RED)Failed to pull Docker images. Please check the logs.$(RESET)"; exit 1; }
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Docker images pulled successfully.$(RESET)"

.PHONY: docker-up
docker-up:
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Starting Docker containers...$(RESET)"
	@docker compose -f $(COMPOSE_FILE) up -d || \
		{ echo "[$(RED)  ERROR  $(RESET)] $(RED)Failed to start Docker containers. Please check the logs.$(RESET)"; exit 1; }
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Docker containers started successfully.$(RESET)"
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Watchtower will check for updates every 24 hours$(RESET)"
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)View logs with: make docker-logs$(RESET)"

.PHONY: docker-down
docker-down:
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Stopping Docker containers...$(RESET)"
	@docker compose -f $(COMPOSE_FILE) down || \
		{ echo "[$(RED)  ERROR  $(RESET)] $(RED)Failed to stop Docker containers.$(RESET)"; exit 1; }
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Docker containers stopped successfully.$(RESET)"

.PHONY: docker-restart
docker-restart: docker-down docker-up
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Docker containers restarted.$(RESET)"

.PHONY: docker-logs
docker-logs:
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Displaying Carousel container logs (Ctrl+C to exit)...$(RESET)"
	@docker logs -f carousel

.PHONY: docker-ps
docker-ps:
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Listing running Docker containers...$(RESET)"
	@docker compose -f $(COMPOSE_FILE) ps

.PHONY: docker-clean
docker-clean:
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Removing Docker containers and volumes...$(RESET)"
	@docker compose -f $(COMPOSE_FILE) down -v || \
		{ echo "[$(RED)  ERROR  $(RESET)] $(RED)Failed to clean Docker containers.$(RESET)"; exit 1; }
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Docker containers and volumes removed.$(RESET)"

.PHONY: docker-deploy
docker-deploy: docker-pull docker-up
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Docker deployment complete!$(RESET)"
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Check status with: make docker-ps$(RESET)"

.PHONY: docker-update
docker-update:
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Updating Docker containers...$(RESET)"
	@docker compose -f $(COMPOSE_FILE) pull
	@docker compose -f $(COMPOSE_FILE) up -d --force-recreate
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Docker containers updated and restarted.$(RESET)"

# ===== Combined setup target =====
.PHONY: setup-dev
setup-dev: install build
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Development environment setup complete.$(RESET)"

.PHONY: setup-docker
setup-docker: docker-pull
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Docker environment setup complete.$(RESET)"
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Start containers with: make docker-up$(RESET)"

# ===== Cleanup targets =====
.PHONY: clean-python
clean-python:
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Cleaning up Python environment...$(RESET)"
	@find src/ -name "*.pyc" -exec rm -f {} + 2>/dev/null || true
	@find src/ -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Python environment cleaned up.$(RESET)"

.PHONY: clean-library
clean-library:
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Cleaning up 'rpi-rgb-led-matrix' build artifacts...$(RESET)"
	@make -C ./rpi-rgb-led-matrix/examples-api-use clean
	@make -C ./rpi-rgb-led-matrix clean
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)'rpi-rgb-led-matrix' build artifacts cleaned up.$(RESET)"

.PHONY: clean
clean: clean-python clean-library
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)All clean operations completed successfully.$(RESET)"

.PHONY: clean-all
clean-all: clean docker-clean
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Complete cleanup (dev + docker) finished.$(RESET)"

# ===== Update target =====
.PHONY: update
update:
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Updating project repository...$(RESET)"
	@git submodule update --remote --merge
	@git pull
	@echo "[$(BLUE)  INFO   $(RESET)] $(BLUE)Updating project dependencies...$(RESET)"
	@pip install --upgrade -e .
	@echo "[$(GREEN) SUCCESS $(RESET)] $(GREEN)Project and dependencies updated successfully.$(RESET)"

# ===== Help target =====
.PHONY: help
help:
	@echo "$(BLUE)Carousel Project - Available Commands:$(RESET)"
	@echo ""
	@echo "$(GREEN)Development:$(RESET)"
	@echo "  make install         - Install Python dependencies"
	@echo "  make build           - Build rpi-rgb-led-matrix library"
	@echo "  make setup-dev       - Complete dev setup (install + build)"
	@echo "  make example         - Run LED matrix demo"
	@echo "  make run             - Run the project"
	@echo "  make dev             - Run with debug logging"
	@echo "  make dev-emulator    - Run in emulator mode with debug"
	@echo ""
	@echo "$(GREEN)Docker Deployment:$(RESET)"
	@echo "  make docker-pull     - Pull latest Docker images"
	@echo "  make docker-up       - Start containers (detached)"
	@echo "  make docker-down     - Stop containers"
	@echo "  make docker-restart  - Restart containers"
	@echo "  make docker-logs     - View carousel container logs"
	@echo "  make docker-ps       - List running containers"
	@echo "  make docker-deploy   - Pull and start containers"
	@echo "  make docker-update   - Pull latest images and recreate containers"
	@echo "  make docker-clean    - Remove containers and volumes"
	@echo "  make setup-docker    - Setup Docker environment"
	@echo ""
	@echo "$(GREEN)Maintenance:$(RESET)"
	@echo "  make clean           - Clean Python and library artifacts"
	@echo "  make clean-all       - Clean everything (dev + docker)"
	@echo "  make update          - Update repository and dependencies"
	@echo "  make help            - Show this help message"