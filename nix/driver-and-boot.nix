{
  lib,
  config,
  pkgs,
  ...
}:

let
  kernel = config.boot.kernelPackages.kernel;

  linuwu-sense = pkgs.stdenv.mkDerivation {
    pname = "linuwu-sense";
    version = "git";
    __structuredAttrs = true;

    src = pkgs.fetchFromGitHub {
      owner = "PXDiv";
      repo = "Div-Linuwu-Sense";
      rev = "d8ea437d847268dd9fe2a49ae28d0723dd720968";
      hash = "sha256-VA8i6kTQ4p5AqSW/jNWJOB4/I4pXV3KKIcrcZ2zHrgM=";
    };

    postPatch = ''
      sed -i 's/\bstrncpy(/memcpy(/' src/linuwu_sense.c
    '';

    nativeBuildInputs = kernel.moduleBuildDependencies;
    hardeningDisable = [
      "pic"
      "format"
    ];

    makeFlags = (lib.filter (f: !(lib.hasPrefix "O=" f)) kernel.makeFlags) ++ [
      "KVER=${kernel.modDirVersion}"
      "KDIR=${kernel.dev}/lib/modules/${kernel.modDirVersion}/build"
    ];

    installPhase = ''
      runHook preInstall
      install -D src/linuwu_sense.ko \
        $out/lib/modules/${kernel.modDirVersion}/kernel/drivers/platform/x86/linuwu_sense.ko
      runHook postInstall
    '';
  };

  kbPath = "/sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/four_zoned_kb";
  psPath = "/sys/module/linuwu_sense/drivers/platform:acer-wmi/acer-wmi/predator_sense";
  stateFile = "${config.users.users.${config.linuwu-sense.user}.home}/.config/linuwu-sense-gui/state.json";

  # Reads the GUI's saved JSON and reapplies it at boot, before login.
  # Needs no GTK -- json is stdlib.
  linuwu-sense-apply =
    pkgs.writers.writePython3 "linuwu-sense-apply"
      {
        flakeIgnore = [
          "E501"
          "E302"
          "E305"
        ];
      }
      ''
        import json

        KB = "${kbPath}"
        PS = "${psPath}"
        STATE = "${stateFile}"


        def write(path, value):
            with open(path, "w") as f:
                f.write(value)


        def main():
            try:
                with open(STATE) as f:
                    state = json.load(f)
            except Exception:
                state = {}

            dim = state.get("boot_dim", False)

            try:
                if not state.get("kb_on", False):
                    write(f"{KB}/four_zone_mode", "0,0,0,1,0,0,0")
                elif state.get("active_mode") == "zone":
                    z = state.get("zone", {})
                    colors = z.get(
                        "colors", ["ff0000", "00ff00", "0000ff", "ffffff"])
                    bright = 0 if dim else z.get("brightness", 100)
                    write(f"{KB}/per_zone_mode",
                          ",".join(colors) + "," + str(bright))
                else:
                    e = state.get("effect", {})
                    r, g, b = e.get("color", [0, 150, 255])
                    mode = e.get("mode", 3)
                    bright = 0 if dim else e.get("brightness", 100)
                    if mode == 0:
                        hx = "{:02x}{:02x}{:02x}".format(r, g, b)
                        write(f"{KB}/per_zone_mode",
                              ",".join([hx] * 4) + "," + str(bright))
                    else:
                        vals = [mode, e.get("speed", 5), bright,
                                e.get("direction", 1), r, g, b]
                        write(f"{KB}/four_zone_mode",
                              ",".join(str(v) for v in vals))
            except Exception:
                pass

            try:
                write(f"{PS}/backlight_timeout",
                      str(state.get("backlight_timeout", 0)))
            except Exception:
                pass

            try:
                cpu = state.get("cpu_fan", 0)
                gpu = state.get("gpu_fan", 0)
                write(f"{PS}/fan_speed", f"{cpu},{gpu}")
            except Exception:
                pass


        if __name__ == "__main__":
            main()
      '';
in
{
  options.linuwu-sense.enable = lib.mkEnableOption "Linuwu-Sense (Acer Predator/Nitro RGB keyboard and platform module)";
  options.linuwu-sense.user = lib.mkOption { type = lib.types.str; description = "User who may control the keyboard and fans, and whose saved state is applied at boot."; };

  config = lib.mkIf config.linuwu-sense.enable {
    boot.extraModulePackages = [ linuwu-sense ];
    boot.blacklistedKernelModules = [ "acer_wmi" ];
    boot.kernelModules = [ "linuwu_sense" ];

    users.groups.linuwu_sense = { };
    users.users.${config.linuwu-sense.user}.extraGroups = [ "linuwu_sense" ];

    systemd.tmpfiles.rules = [
      "f ${kbPath}/four_zone_mode 0660 root linuwu_sense - -"
      "f ${kbPath}/per_zone_mode 0660 root linuwu_sense - -"
      "f ${psPath}/fan_speed 0660 root linuwu_sense - -"
      "f ${psPath}/usb_charging 0660 root linuwu_sense - -"
      "f ${psPath}/battery_limiter 0660 root linuwu_sense - -"
      "f ${psPath}/backlight_timeout 0660 root linuwu_sense - -"
    ];

    systemd.services.linuwu-sense-apply-boot = {
      description = "Apply saved Predator RGB/fan/timeout state at boot";
      wantedBy = [ "multi-user.target" ];
      after = [ "systemd-modules-load.service" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${linuwu-sense-apply}";
      };
    };
  };
}
