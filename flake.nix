{
  description = "Ojuny minimal installer - TTY installer ISO for Ojuny templates";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs.nixpkgs-lib.follows = "nixpkgs";
    };

    ojuny-minimal-template = {
      url = "github:ojuny-project/ojuny-minimal-template";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    inputs@{
      self,
      flake-parts,
      nixpkgs,
      ...
    }:
    let
      system = "x86_64-linux";

      iso = nixpkgs.lib.nixosSystem {
        inherit system;
        specialArgs = { inherit inputs; };
        modules = [ ./nixos/iso.nix ];
      };

      testIso = nixpkgs.lib.nixosSystem {
        inherit system;
        specialArgs = { inherit inputs; };
        modules = [
          ./nixos/iso.nix
          ./nixos/test.nix
        ];
      };
    in
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ system ];

      perSystem =
        { pkgs, ... }:
        let
          installer = pkgs.callPackage ./installer { };
          python = pkgs.python3;
        in
        {
          packages = {
            ojuny-install = installer;
            ojuny-minimal-iso = iso.config.system.build.isoImage;
            ojuny-minimal-iso-test = testIso.config.system.build.isoImage;
          };

          apps.install = {
            type = "app";
            program = "${installer}/bin/ojuny-install";
          };

          apps.ci = {
            type = "app";
            program = "${
              pkgs.writeShellApplication {
                name = "ci";
                runtimeInputs = [ pkgs.nix ];
                text = ''
                  exec nix flake check "$@"
                '';
              }
            }/bin/ci";
          };

          devShells.default = pkgs.mkShell {
            packages = with pkgs; [
              deadnix
              git
              jq
              nix
              nixfmt
              OVMF
              python3
              qemu
              shellcheck
              squashfsTools
              statix
              xorriso
            ];
          };

          checks = {
            format =
              pkgs.runCommand "check-format"
                {
                  nativeBuildInputs = [ pkgs.nixfmt ];
                }
                ''
                  cd ${./.}
                  nixfmt --check flake.nix installer/default.nix nixos/*.nix
                  touch $out
                '';

            python =
              pkgs.runCommand "check-python"
                {
                  nativeBuildInputs = [ python ];
                }
                ''
                  for file in ${./installer}/oj_installer/*.py; do
                    ${python}/bin/python3 -c 'import ast, sys; ast.parse(open(sys.argv[1]).read())' "$file"
                  done
                  touch $out
                '';

            installer-help =
              pkgs.runCommand "check-installer-help"
                {
                  nativeBuildInputs = [ installer ];
                }
                ''
                  ojuny-install --help > $out
                '';

            fixed-paths =
              pkgs.runCommand "check-fixed-paths"
                {
                  nativeBuildInputs = [ python ];
                }
                ''
                  ${python}/bin/python3 ${./tests/check-fixed-paths.py} --root ${./.}
                  touch $out
                '';

            flake-structure =
              pkgs.runCommand "check-flake-structure"
                {
                  nativeBuildInputs = [ pkgs.diffutils ];
                }
                ''
                  cmp ${./installer/oj_installer/flake_structure.py} ${inputs.ojuny-minimal-template}/scripts/flake_structure.py
                  touch $out
                '';

            layout-plan =
              pkgs.runCommand "check-layout-plan"
                {
                  nativeBuildInputs = [ python ];
                }
                ''
                  PYTHONPATH=${./installer} ${python}/bin/python3 ${./tests/check-layout-plan.py}
                  touch $out
                '';

            settings =
              pkgs.runCommand "check-settings"
                {
                  nativeBuildInputs = [ python ];
                }
                ''
                  PYTHONPATH=${./installer} ${python}/bin/python3 ${./tests/check-settings.py}
                  touch $out
                '';

            iso-size =
              pkgs.runCommand "check-iso-size"
                {
                  nativeBuildInputs = [ pkgs.coreutils ];
                }
                ''
                  size=$(stat -c %s ${iso.config.system.build.isoImage}/iso/*.iso)
                  echo "minimal ISO: $size bytes"
                  test "$size" -le 1600000000 || {
                    echo "minimal ISO exceeds 1.6 GB"
                    exit 1
                  }
                  touch $out
                '';

            default = pkgs.runCommand "check-default" { } ''
              echo ${self.checks.${system}.format} >/dev/null
              echo ${self.checks.${system}.python} >/dev/null
              echo ${self.checks.${system}.installer-help} >/dev/null
              echo ${self.checks.${system}.fixed-paths} >/dev/null
              echo ${self.checks.${system}.flake-structure} >/dev/null
              echo ${self.checks.${system}.layout-plan} >/dev/null
              echo ${self.checks.${system}.settings} >/dev/null
              echo ${self.checks.${system}.iso-size} >/dev/null
              touch $out
            '';
          };
        };

      flake = {
        hydraJobs = self.checks;
        nixosConfigurations.ojuny-minimal-iso = iso;
      };
    };
}
