# linuwu-sense-gui

GTK4 GUI for [Linuwu-Sense](https://github.com/PXDiv/Div-Linuwu-Sense):
RGB keyboard (effects and per-zone colors), fan control, auto-off timeout,
and a "start at 0 brightness after restart" option for Acer Predator/Nitro laptops.

Tested only on the Predator PHN16-71 under NixOS.

## Files
- `linuwu-sense-gui.py`: the GTK4 app
- `nix/gui.nix`: Home Manager packaging
- `nix/driver-and-boot.nix`: builds the driver and applies saved state at boot

## Note
Set `linuwu-sense.enable = true;` and `linuwu-sense.user = "yourusername";` in your NixOS config.

## Credits
Driver: Linuwu-Sense (PXDiv fork). This project is an independent GUI and
contains none of the driver code.
