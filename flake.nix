{
  description = "ai-onboard - ambiente Python para estudo e uso de LLMs";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python312;
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            python
            python.pkgs.pip
            python.pkgs.virtualenv
            pkgs.uv
          ];

          shellHook = ''
            echo "ai-onboard :: Python $(python --version)"
            if [ ! -d .venv ]; then
              python -m venv .venv
            fi
            source .venv/bin/activate
          '';
        };
      });
}
