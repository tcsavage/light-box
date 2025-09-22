# Light Box

This is a [Micropython](https://micropython.org/) project for animating NeoPixel LEDs using a [Raspberry Pi Pico](https://www.raspberrypi.org/documentation/microcontrollers/micropython.html) to simulate flashing emergency vehicle lights - a fun little toy for my son.


# Core Abstractions

## NeoPixel

This program makes use of the [NeoPixel Micropython library](https://docs.micropython.org/en/latest/library/neopixel.html) to control the NeoPixel LEDs. In this case, they're arranged in two rings daisy-chained together, controlled by a single data line.

Since there's a single data line controlling two rings, it's desirable for some animations to "bifurcate" the chain into two halves. The `NeoPixelBlock` class allows you to create a "view" into a contiguous subset of the NeoPixel chain. The indexing fr each "block" is zero-based, so the first pixel in the block is always index 0.

Given two `NeoPixelBlock` instances (or indeed two raw `NeoPixel` instances), the `NeoPixelReplicate` class allows you to combine them into a single logical NeoPixel instance that replicates the data to both underlying instances.

With these two classes over the NeoPixel class, you can split the NeoPixel chain into two halves, and then replicate animations to both halves - all while using a single NeoPixel data line.

## ColorF

The NeoPixel library uses tuples of integers in the range 0-255 to represent colors. This is a bit clunky to work with when doing color math, so the `ColorF` class is a simple class that represents colors as floating point values in the init interval [0.0, 1.0]. It can convert to the integer tuple format used by the NeoPixel library, and it supports basic color operations (like `scale_brightness` and `mix`).

## Animation

An animation is effectively a function that maps a time and a pixel "index" to a `ColorF`. Both inputs are floating point values in the unit interval [0.0, 1.0].

There are a few "base" animations implemented (e.g. `AnimationFlash`, `AnimationSpinner`), as well as some combinators that allow you to combine or modify animations in various ways:

- `MixedAnimation` - evaluates a collection of animations together and mixes the results together
- `TimeShiftedAnimation` - shifts the time input by a fixed amount
- `SpeedAdjustedAnimation` - scales the time input by a fixed multiplier
- `ConcatenatedAnimation` - runs a sequence of animations one after another (scales the time input to fit)
- `ReverseAnimation` - reverses the time input (i.e. `t` becomes `1.0 - t`)
- `RemapAnimation` - trims the time input to a sub-interval and remaps it to [0.0, 1.0]
- `BakedAnimation` - pre-evaluates an animation at a fixed number of steps and then uses a naive lookup for fast evaluation

## Renderer

A `Renderer` joins an `Animation` to a `NeoPixel` (or `NeoPixel`-like) instance. The `render(t)` method takes the current time in the unit interval [0.0, 1.0], evaluates the animation for each pixel in the NeoPixel instance, and writes the resulting colors to the NeoPixel instance.

A `Renderers` is simply a collection of `Renderer` instances that can all be rendered together.

## Timeline

A `Timeline` is simply a keeper of time, providing a `t` value in the unit interval [0.0, 1.0] that loops over a fixed duration.

# Putting it all together

Here's an example of bifurcating a NeoPixel chain into two halves, creating an animation, and rendering slightly adjusted versions of the animation to each half:

```python
def make_color_flash_renderer(np, color):
    flash_anim = SpeedAdjustedAnimation(AnimationFlash(color), speed=1.5)
    np_block1 = NeoPixelBlock(np, 0, n//2)
    np_block2 = NeoPixelBlock(np, n//2, n)
    renderer = Renderers(
        Renderer(np_block1, flash_anim),
        Renderer(np_block2, TimeShiftedAnimation(flash_anim, 0.5)),
    )
    return renderer
```
