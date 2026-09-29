{ pkgs, ... }:

let
  pythonEnv = pkgs.python3.withPackages (ps: [
    ps.pygobject3
    ps.pycairo
  ]);

  predator-control = pkgs.stdenv.mkDerivation {
    pname = "predator-control";
    version = "0.2.0";
    dontUnpack = true;

    nativeBuildInputs = [
      pkgs.wrapGAppsHook4
      pkgs.gobject-introspection
      pkgs.makeWrapper
    ];
    buildInputs = [ pkgs.gtk4 ];

    installPhase = ''
            mkdir -p $out/share/predator-control $out/bin $out/share/applications
            install -m644 ${../linuwu-sense-gui.py} $out/share/predator-control/predator-control.py

            makeWrapper ${pythonEnv}/bin/python3 $out/bin/predator-control \
              --add-flags "$out/share/predator-control/predator-control.py"

            cat > $out/share/applications/predator-control.desktop <<EOF
      [Desktop Entry]
      Type=Application
      Name=Predator Control
      Comment=Keyboard RGB and fan control
      Exec=$out/bin/predator-control
      Icon=input-keyboard
      Categories=Settings;HardwareSettings;
      EOF
    '';
  };
in
{
  home.packages = [ predator-control ];

  xdg.configFile."autostart/predator-control-apply.desktop".text = ''
    [Desktop Entry]
    Type=Application
    Name=Predator Control (apply saved state)
    Exec=${predator-control}/bin/predator-control --apply-saved
    NoDisplay=true
    X-GNOME-Autostart-enabled=true
  '';
}
