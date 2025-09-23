# Overview

This is a web scraping automation system that extracts insurance claim data from BCI Seguros and Zenit insurance company portals and integrates it with Notion databases. The application uses Selenium for web automation, Flask for providing a streaming API endpoint, and the Notion API for data management.

The system automates the process of logging into insurance portals, navigating through different company contexts (BCI/Zenit), scraping claim information, and organizing this data into structured Notion databases for tracking and management purposes.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Web Scraping Engine
The core scraping functionality is built around Selenium WebDriver with stealth capabilities to avoid detection. The scraper supports multi-company contexts, automatically switching between BCI and Zenit portals within the same session. It includes robust error handling, popup management, and context detection to ensure reliable data extraction.

## Flask Streaming API
The application uses Flask to provide a RESTful endpoint that streams real-time progress updates during the scraping process. This streaming approach allows clients to monitor the automation progress without blocking, using Server-Sent Events (SSE) pattern for live feedback.

## Data Processing Pipeline
Scraped data flows through a processing pipeline that extracts, validates, and formats insurance claim information before sending it to Notion. The system handles various data types including dates, currency amounts, and structured claim details.

## Notion Integration Layer
The NotionManager class handles all interactions with Notion's API, including creating pages in multiple databases (siniestros, patentes, clientes), applying templates, and managing relationships between different data entities. It includes comprehensive error handling and retry logic for API operations.

## Browser Automation Architecture
The system uses standard Selenium WebDriver with stealth modifications to avoid bot detection. It includes sophisticated popup handling, context switching between insurance companies, and robust waiting mechanisms to handle dynamic content loading.

# External Dependencies

## Web Automation
- **Selenium WebDriver**: Core browser automation framework
- **selenium-stealth**: Anti-detection capabilities for web scraping
- **webdriver-manager**: Automatic browser driver management
- **BeautifulSoup4**: HTML parsing and manipulation
- **2captcha-python**: CAPTCHA solving service integration

## Data Processing
- **pandas**: Data manipulation and analysis
- **pdfplumber**: PDF document processing
- **openpyxl**: Excel file handling

## Web Framework
- **Flask**: Web server framework for API endpoints
- **gunicorn**: WSGI HTTP server for production deployment

## External Services
- **Notion API**: Database and workspace management
- **BCI Seguros Portal**: Primary insurance claims system
- **Zenit Portal**: Secondary insurance claims system
- **2captcha Service**: Automated CAPTCHA solving

## Environment Management
- **python-dotenv**: Environment variable management
- **zoneinfo/tzdata**: Timezone handling for date processing

The system is designed to run in containerized environments and includes proper error handling, logging, and progress reporting throughout the automation pipeline.