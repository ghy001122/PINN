# Device Anchor

The first engineering version is anchored by an **Nb/NbOx/V2O5/Ni** interface-engineered oxide memristor structure.

This model is hardware-inspired and literature-guided, not a direct replication of all microscopic processes in the cited device.

## Software Variables and Hardware Mapping

- `c_v`: effective defect / oxygen-vacancy state.
- `T`: local Joule-heating temperature.
- `m`: effective conductive-state fraction.
- `gamma_sub`: coarse-grained electrode/substrate/interface thermal dissipation.
- `A_eff`: effective electrically active area.

## Scope

The first version intentionally uses a one-dimensional electro-thermal-defect-conductive-state model. It avoids unvalidated claims about full 3D electromagnetics, complete phase-field free energy, exact Schottky boundary emission, or real device fabrication performance.
