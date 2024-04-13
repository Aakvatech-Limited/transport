# Transport Management System Module

## Overview
This module is designed to enhance the capabilities of ERPNext in managing transportation and logistics operations. It integrates various functionalities including vehicle management, trip planning, document management, expense tracking, and compliance checks. This module aims to streamline operations, ensure regulatory compliance, and optimize route and resource allocation.

## Features
- **Document Management**: Manage and track driver and vehicle documents with automatic alerts for document expiry.
- **Vehicle Tracking**: Real-time tracking of vehicle locations, statuses, and operational metrics.
- **Expense Management**: Comprehensive management of fixed and variable expenses related to transportation.
- **Checklists and SOPs**: Standardized procedures for vehicle and driver checks to maintain safety and compliance standards.
- **Trip Management**: Detailed management of routes, assignments, and trip-related expenses and documents.

## Installation

### Prerequisites
- ERPNext: version 13.x or later
- Frappe Framework: version 13.x or later

### Steps
1. Clone the repository:
   ```bash
   git clone https://github.com/aakvatech/transport.git
   cd transportation_management_system
   ```

2. Install the module:
   ```bash
   bench get-app https://github.com/aakvatech/transport.git
   bench --site your-site-name install-app transms
   ```

## Configuration
- Configure the transport settings via:
  - Home > Transport Management > Settings > Transport Settings
- Set up document expiry alerts and vehicle tracking from:
  - Home > Transport Management > Reports

## Usage
- To start using the module, navigate to:
  - Home > Transport Management
- Access various features such as Vehicle Management, Trip Planning, Document Management, etc., through the module's dashboard.

## Documentation
For further documentation on each Doctype and Report, refer to:
- `docs/`
- [Online Documentation](https://github.com/aakvatech/transport/README.md)

## Support
For issues and support, please create a support ticket:
- **Issue Tracker**: https://github.com/aakvatech/transport/issues

## Contributing
Contributions to the module are welcome. Please fork the repository, make your changes, and submit a pull request.

## License
This project is licensed under the [MIT License](LICENSE). See the LICENSE file for more details.
