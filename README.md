# pymmcore-gui

This is a stub repo for discussing a unified effort towards a GUI application for [`pymmcore-plus`](https://github.com/pymmcore-plus/pymmcore-plus) & [`pymmcore-widgets`](https://github.com/pymmcore-plus/pymmcore-widgets)

<details>
  <summary><em>For developers</em></summary>

  <h2>This repo now contains a working GUI prototype 🎉🚀</h2>

  See [CONTRIBUTING](CONTRIBUITING.md) for more information on how to get started.

</details>

## Goals (and non-goals) of unification

**Goals**

- Provide a napari-independent GUI for controlling micro-manager via pymmcore-plus (i.e. pure python micro-manager control).  We'd like to have a primary application that we can point interested parties to (rather than having to describe all the related efforts and explain how to compose pymmcore-widgets directly).
- Avoid duplicate efforts.  While independent related projects are excellent in that they allow rapid exploration and experimentation, we'd like to be able to share the results of these efforts.  In some ways that is done via pymmcore-widgets, but all of the application level stuff (persistence of settings, complex layouts, coordination of data saving, viewing & processing) is explicitly not part of pymmcore widgets.
- Establish patterns for persistence and application state.

**Non-Goals**

- Working on a shared application is *not* meant to discourage independent experimentation and repositories.  (One of the real strengths in doing this all in python is the ease of creating custom widgets and GUIs!).  One possible pattern would be forks & branches off of a main central repository.

## Purpose of this repo

For now, this serves as place to store TODO issues and discussion items.  Please open an issue if you are interested, (even just to say hi! 🙂)

## Existing Efforts

### napari-micromanager

<img width="1840" alt="napari-micromanager" src="https://github.com/pymmcore-plus/napari-micromanager/assets/1609449/e1f395cd-2d57-488e-89e2-b1923310fc2a">

An initial effort towards a pure python micro-manager gui based on the pymmcore-plus ecosystem was [napari-micromanager](https://github.com/pymmcore-plus/napari-micromanager). It uses [napari](https://github.com/napari/napari) as the primary viewer, and [pymmcore-widgets](https://github.com/pymmcore-plus/pymmcore-widgets) for most of the UI related to micro-manager functionality. It still works and will continue to be maintained for the foreseable future, but we are also interested in exploring options that do not depend on napari.

One candidate to replace the viewing functionality provided by napari is [`ndv`](https://github.com/pyapp-kit/ndv), a slim multi-dimensional viewer with minimal dependencies.  Two experimental efforts exist to build a micro-manager gui using ndv

### micromanager-gui

<img width="1840" alt="Screenshot 2024-06-03 at 11 49 45 PM" src="https://github.com/fdrgsp/micromanager-gui/assets/70725613/d8148931-1153-405e-96d6-67abe57f88a3">

[micromanager-gui](https://github.com/fdrgsp/micromanager-gui) is a standalone application written by Federico Gasparoli ([@fdrgsp](https://github.com/fdrgsp)), and currently lives in federico's personal org while we experiment with it.

### pymmcore-plus-sandbox

<img width="1190" alt="Screenshot 2024-10-13 at 2 50 57 PM" src="https://github.com/user-attachments/assets/cd1d81aa-1bab-48ca-ad31-420dc08e72a5">

[`pymmcore-plus-sandbox`](https://github.com/gselzer/pymmcore-plus-sandbox) is another experimental standalone GUI written by Gabe Selzer ([@gselzer](https://github.com/gselzer) with input from [@marktsuchida](https://github.com/marktsuchida).  One initial goal here is to create a main window that looks very similar to the java based MMStudio (which would make it familiar to existing users of the java ecosystem).

### LEB-EPFL

Willi Stepp ([@wl-stepp](https://github.com/wl-stepp)) has been an active contributor to pymmcore-widgets and uses some of these widgets in his event-driven microscopy controllers.
