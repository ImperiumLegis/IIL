# Security reporting

Report suspected security issues privately to the repository owner through the contact details on the owner's [GitHub profile](https://github.com/oneezeeroo). If private vulnerability reporting is enabled on the repository, use the **Report a vulnerability** button on its Security tab.

Include the commit or package version, affected review profile, expected verdict, observed verdict, and a minimal synthetic proposal if available. Remove keys, receipts from active sessions, customer data, and provider credentials. Public issues are suitable for documentation and routine defects. Coordinate public disclosure of a security issue with the maintainer after a fix is available.

The public core evaluates operator-supplied policy and verifies review evidence. Execution isolation, secret custody and atomic consumption of a receipt belong to the deployment that controls the provider credential. See the [threat model](docs/THREAT_MODEL.md).
