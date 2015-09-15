Netman's REST API documentation!
================================

.. toctree::
   :maxdepth: 4

Currently supported hardware and features
-----------------------------------------

==============   ===============   ====================   =============   ===============
Switch model     Bond management   Interface management   IP management   VLAN management
==============   ===============   ====================   =============   ===============
Brocade XXXX     No                Yes                    Yes             Yes
Cisco 2950       No                Yes                    Yes             Yes
Cisco 3750       No                Yes                    Yes             Yes
Cisco 6500       No                Yes                    Yes             Yes
Juniper EX2200   Yes               No                     No              Yes
Juniper QFX      Yes               No                     No              Yes
Dell             No                Yes                    No              Yes
==============   ===============   ====================   =============   ===============

API documentation
-----------------

.. autoflask:: netman.main:app
   :undoc-static:
   :include-empty-docstring:

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

