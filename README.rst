asv-bwrap
=========

Manage running asv_ benchmarks in a lightweight Bubblewrap_
sandbox on Linux.

Collects results and HTML output to a Git repository, which is
optionally pushed to a remote location.

.. _asv: https://github.com/airspeed-velocity/asv/
.. _Bubblewrap: https://github.com/projectatomic/bubblewrap


Example
-------

::

    user$ asv-bwrap --sample-config > config.toml
    user$ vi config.toml
    user$ asv-bwrap config.toml run master^!

    # echo 'su -c "asv-bwrap config.toml run NEW" - user' > /etc/cron.daily/run-benchmarks
    # chmod +x /etc/cron.daily/run-benchmarks

Configuration
-------------

To get a sample configuration file, run ``asv-bwrap --sample-config > config.toml``.

It contains settings for the work directory, sandboxing, etc., and the
shell scripts to run inside the sandbox. *asv-bwrap* comes with a
set of default scripts, which work for the most common configurations.


Sandboxing
----------

*asv-bwrap* builds a lightweight sandbox using Bubblewrap_.

It launches the worker scripts in a new filesystem namespace, which
exposes ``/usr``, ``/lib`` etc. common locations as read-only.
Directories for storing json result files and html output are
available read-write.

The sandbox container is likely difficult to escape from, and can
protect against mistakes in benchmark scripts, without affecting
performance as much as a virtual machine.

**However**, the net namespace is not unshared, so processes inside the
sandbox can access also local network resoures. If you want to use
this to run untrusted code, you need to review firewall rules and
other aspects of the configuration.

*asv-bwrap* should not be run as root.

All operations on the results repository are done outside the sandbox,
including uploading.
