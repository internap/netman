# Nomenclature to be used for switch methods

# Lists
### Adding
* Should be called add_*
* Should raise if it exists

### Removing
* Should be called remove_*
* Should raise if it does not exist

### Fetching
* Should be called get_*
* Should raise if it does not exist

### Enumerating
* Should be called get_*s
* Each entry should contain the equivalent of a fetch


# Values
Name should contain parent resource (e.g. interface_port_mode, interface_access_vlan)

### Setting
* Should be called set_*
* Should overwrite if already set

### Unsetting
* Should be called unset_*
* Should not raise if not set

### Fetching
* Should be called get_*
* Should not raise if not set


# Booleans
Name should contain parent resource (e.g. interface_port_mode, interface_access_vlan)

### Setting
* Should be called set_*_state
* Should overwrite if already set

### Unsetting
* Should be called unset_*
* Should not raise if not set

### Fetching
* Should be called get_*
* Should not raise if not set