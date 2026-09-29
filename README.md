# linuwu-sense-gui

A simple GTK4 app to control the RGB keyboard and fans on Acer Predator/Nitro laptops (NixOS).
It is a GUI for [Linuwu-Sense](https://github.com/PXDiv/Div-Linuwu-Sense).

Features: keyboard effects, per-zone colors, fan control, auto-off timeout,
and an option to start at 0 brightness after restart.

Tested only on the Predator PHN16-71.

## Install

1. Copy this whole folder into your NixOS config, for example `~/.dotfiles/linuwu-sense-gui/`.

2. In your **NixOS** config, add:

```nix
imports = [ ./linuwu-sense-gui/nix/driver-and-boot.nix ];

linuwu-sense.enable = true;
linuwu-sense.user = "yourusername";
```

3. In your **Home Manager** config, add:

```nix
imports = [ ./linuwu-sense-gui/nix/gui.nix ];
```

4. If you use git or flakes, run `git add .` so Nix can see the new files.

5. Rebuild, then **reboot** (the driver replaces the stock acer_wmi module):

```bash
sudo nixos-rebuild switch --flake . # or "nh os switch" (if you use nh)
home-manager switch --flake . # or "nh home switch" (if you use nh)
sudo reboot
```


Adjust the rebuild commands to how you normally rebuild.

## Run

Open **Predator Control** from your app menu, or run `predator-control` in a terminal.

Your last settings are saved and re-applied automatically at boot.

## Credits

Driver: Linuwu-Sense (PXDiv fork). This project is an independent GUI and contains none of the driver code.
