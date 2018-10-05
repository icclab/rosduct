^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Changelog for package rosduct
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

0.0.5 (2018-10-05)
------------------
* removed cuplicate dep
* removed cuplicate dep
* removed cuplicate dep
* Merge branch 'cwbollinger-master'
* Merge branch 'master' of https://github.com/cwbollinger/rosduct into cwbollinger-master
* Added services to remove topic/service from bridge
* Added services to dynamically expose topic/service
* Commented out over-verbose logging
* Exit rosduct when connection is broken.
  Can't seem to recover afterwards, so might as well exit
* Experiments to enable reconnections
* Contributors: Chris Bollinger, Marc Hanheide, christopheriksen

0.0.4 (2018-09-03)
------------------
* Merge pull request `#2 <https://github.com/LCAS/rosduct/issues/2>`_ from MFernandezCarmona/master
  Update package.xml
* reintroduced pydispatcher
* remove pydispatch
  the problem is we need `pip install pydispatcher`, not `pydispatch` . So for now we remove this dependency until we have a deb package for this python package
* Caching Service exceptions...
* Update conversions.py
* Update package.xml
  These should solve the following errors I had runing rosduct:
  ImportError: No module named ws4py.client.threadedclient
  ImportError: No module named pydispatch
* Contributors: Manuel Fernandez-Carmona, Marc Hanheide

0.0.3 (2018-08-19)
------------------
* latching was a stupid idea
* Contributors: Marc Hanheide

0.0.2 (2018-08-19)
------------------
* latch remote topics
* latch remote topics
* Contributors: Marc Hanheide

0.0.1 (2018-07-17)
------------------
* adopted for release
* Extending README with docker use case
* Add note about rosout
* Add support for remapping, a way for dealing with multiple robots
* Add support for services
* Cleanup docs and add test for params
* Added efficient management of rosbridge subscribers
* Update client, latest version supports general introspection calls and param handling
* optimize publication
* Fixes to make it work, damn closures
* Initial commit
* Contributors: Marc Hanheide, Sammy Pfeiffer
