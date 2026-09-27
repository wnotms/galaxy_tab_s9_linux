The first v3 host test run was interrupted while the stage recorder waited in
a global host sync (WSL request_wait_answer). Configfs fixture tests now mock
sync only; they check record contents, not host filesystem durability. Device
sync calls remain real. The rerun passed 26 USB tests in 27.452 seconds, and
74 related debug-channel tests passed in 1.161 seconds. Shell syntax and the
ccache production build passed. No full regression was run for this scope.
