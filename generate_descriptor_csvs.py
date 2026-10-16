"""Generate canonical per-event descriptor CSVs from configured XML results."""

from csv_lib import generate_event_csvs, main

__all__ = ['generate_event_csvs']


if __name__ == '__main__':
    main()