# ISOLDE Offline Optimizer

This package provides COI (CERN optimization interfaces) optimization environments for the ISOLDE Offline facilities at CERN, optimizing beam transport.

## Features

- **YOL1 optimization environment**: Steerers and quadrupoles with configurable FC acquisition
- **YOL2 optimization environment**: Steerers and quadrupoles with configurable FC and WireScanner acquisition
- **Hierarchical data structure**: Automatic run and iteration tracking with structured data directories (`run_XXX/it_YYY/`)
- **Real-time visualization**: Matplotlib-based beam size plotting (horizontal/vertical sigma) over iterations
- **Configurable parameters**: Per-parameter enable/disable, scaling, and convergence tolerances
- **Cancellation support**: Full cancellation token integration for all acquisition operations
- **Utilities**: Wire scanner functions in bsc_methods.py, event builder for JAPC subscriptions, and event serialization
- **Debug mode**: Testing mode that bypasses hardware changes

## Project Structure

```
isolde_offline_optimizer/
├── __init__.py              # Package initialization and exports
├── todos.py                 # Project todos and notes
├── envs/
│   ├── __init__.py          # Environment module initialization
│   ├── base_env.py          # Base class for BTY line optimization
│   └── env_yol1.py          # YOL1 optimization environment
│   └── env_yol2.py          # YOL2 optimization environment
├── utils/
│   ├── __init__.py          # Utility exports
│   ├── bsc_methods.py       # wire scanner methods called from base_env
│   ├── event_acq.py         # Generic event builder for JAPC subscriptions
│   ├── event_serializer.py  # Event serialization utilities
│   └── params.py            # Parameter configuration dataclass
│   └── utils_pjlsa.py       # Functions for controlling accelerator devices
├── playground/
│   ├── 001_tapestation_acquisition.py  # Tapestation acquisition testing
│   ├── 002_all_acquisition.py          # Full acquisition testing
│   └── antons_complaint.txt            # Development notes
└── tests/
    └── test_env.py                      # Environment tests
```

## Architecture

### Base Class

`IsoldeOfflineBaseEnv` provides common optimization logic for offline environments:
- Parameter management with configurable scaling and per-parameter tolerances
- Multi-acquisition averaging for improved statistical accuracy (configurable via `_n_acqs_avg`)
- LSA integration for trimming magnet settings with transient mode
- Cycle-by-cycle event acquisition with full cancellation support
- Parameter convergence monitoring with automatic retries
- Selector validation to ensure environment matches timing configuration
- Hierarchical data structure with automatic run numbering (`run_XXX/it_YYY/`)
- Real-time beam size tracking and visualization support

### Specialized Environments

`IsoldeOfflineEnv` in env_yol1.py and env_yol2.py inherit from the base class:
- **Parameter Configuration**: Each environment defines its specific parameter sets (steerers and quadrupoles) with individual enable/disable, scaling, and tolerance settings
- **Beam presence monitoring**: detector and scanner subscriptions for intensity validation
- **Data organization**: Hierarchical structure per facility

### Acquisition Devices

Modular acquisition system supporting different measurement devices:
- **Faraday Cups**: e.g. fc80, fc100
- **Wire Scanners**: e.g. bs70, bs100
- **GenericEventBuilder**: Groups JAPC subscriptions by cycle stamp for synchronized measurements
  - Buffering of incomplete events with configurable size
  - Iterator and context manager support
  - Thread-safe operation with automatic subscription management
  - `last_event()` method for retrieving most recent complete event
  - Configurable timeout and first-update handling

## API Reference

### Main Classes

#### `IsoldeOffline1Env`

Optimization environment for YOL1.

- **Parameters**: under _setup_parameters (steerers and quadrupoles)
- **Acquisition**: _detector_subscriptions contains faraday cups and _scanner_subscriptions contains wire scanners.
- **Data output**: ./YOL1/run_XXX/it_YYY/ (with extref/ subdirectory for frequency scans)

#### `IsoldeOffline2Env`

Optimization environment for YOL1.

- **Parameters**: under _setup_parameters (steerers and quadrupoles)
- **Acquisition**: _detector_subscriptions contains faraday cups and _scanner_subscriptions contains wire scanners.
- **Data output**: ./YOL1/run_XXX/it_YYY/ (with extref/ subdirectory for frequency scans)

#### `GenericEventBuilder`

Event builder for grouping JAPC subscriptions by cycle stamp:
- Groups parameter subscriptions by cycle stamp and selector
- Provides complete events when all parameters are ready
- Iterator interface for cycle-by-cycle event retrieval
- `start()` and `stop()` methods for subscription management
- `last_event()`: Returns the most recent complete event
- `next_event()`: Blocks until next complete event or timeout
- Context manager support (`with` statement)
- Thread-safe buffering with configurable buffer size
- Automatic cleanup of old incomplete events to prevent memory leaks
- Configurable `ignore_first_updates` option for subscription initialization

### Utility Classes

#### `ParamConfig`

Configuration dataclass for optimization parameters:
- `enabled`: Whether parameter is enabled for optimization
- `addr`: Parameter address for LSA/JAPC access
- `scale`: Scaling factor for parameter values
- `tolerance`: Tolerance for parameter convergence
- `units`: Units of parameter value

#### `serialize_event`

Utility function for serializing acquisition events to JSON format:
- Converts `PropertyRetrievalResponse` objects to JSON-serializable dictionaries
- Handles numpy arrays, scalars, and nested data structures
- Preserves cycle stamps, selectors, and all data fields
- Returns structure: `{param_name: {cycle_stamp, selector, data}}`
- Also provides `serialize_parameter_data()` for single parameter serialization

### Visualization

The environments support real-time visualization through the `render()` method:
- **matplotlib_figures mode**: Returns updated figures showing beam size evolution
- **iter_updates()**: Generator that updates figures with horizontal and vertical beam sigma over iterations
- **Beam size tracking**: Automatic history tracking of sigma_h and sigma_v for each iteration
- **Integration**: Works with `FigureRenderer` from `cernml.mpl_utils`

### Data Organization

Acquisitions are saved in a hierarchical structure:
- **Run-level**: `./YOL1/run_XXX/` or `./YOL2/run_XXX/` (auto-incremented per optimization run)
- **Iteration-level**: `run_XXX/it_YYY/` (one directory per iteration)
- **Standard acquisitions**: `run_XXX/it_YYY/timestamp.json`
- **Frequency scans**: `run_XXX/it_YYY/extref/timestamp.json` (when `enable_extrreffreq` is True)
