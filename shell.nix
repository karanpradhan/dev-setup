{
  pkgs ? import <nixpkgs> { },
}:

pkgs.mkShell {
  packages = with pkgs; [
    treefmt
    nixfmt-rfc-style
    ruff
    stylua
    nodePackages.prettier
    taplo
    pre-commit
    python311
  ];
}
