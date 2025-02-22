{
  description = "Tool for managing boxes when moving";
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    ...
  }:
    flake-utils.lib.eachDefaultSystem
    (
      system: let
        pkgs = import nixpkgs {
          inherit system;
        };
        python = pkgs.python312;
        buildInputs = [
          (python.withPackages (ps:
            with ps; [
              # packages not specified in pyproject.toml: these will be available in the venv.
            ]))
          pkgs.pdm
          pkgs.pre-commit
          pkgs.nodePackages.prettier
          pkgs.texliveSmall
        ];
        # allow building c extensions
        env = {
          LD_LIBRARY_PATH = "${pkgs.stdenv.cc.cc.lib}/lib";
        };
      in {
        devShells.default = pkgs.mkShell {
          inherit buildInputs;
          inherit env;
          shellHook = ''
            pre-commit install
          '';
        };
      }
    );
}
