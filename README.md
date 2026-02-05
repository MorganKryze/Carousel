![screenshot](./docs/assets/img/render.png)

## Overview

Carousel is a Raspberry Pi Zero-powered LED matrix display framework designed to support custom applications and extensible functionality.

## Key features

### Apps

- [x] Main screen / Clock
- [x] Gif viewer
- [x] Conways game of life
- [ ] Weather[^1]
- [ ] Notion todo lists[^2]
- [ ] Pomodoro timer
- [ ] Spotify player[^3]
- [ ] Stocks & crypto
- [ ] Youtube subscribers count

Feel free to suggest new apps by [creating an issue](https://github.com/MorganKryze/Carousel/issues) on the repository!

## Documentation

Comprehensive guides to help you get started:

1. [Wiring Guide](./docs/wiring.md)
2. [Installation Guide](./docs/installation.md)
3. [Configuration Guide](./docs/configuration.md)
4. [rpi-rgb-led-matrix Library Documentation](https://github.com/hzeller/rpi-rgb-led-matrix/blob/f0e95d3557dfc60759a290300c184074e9ec5874/README.md)

## Troubleshooting

If you encounter wiring-related issues, please consult the [Wiring Guide](./docs/wiring.md) or the official [rpi-rgb-led-matrix wiring documentation](https://github.com/hzeller/rpi-rgb-led-matrix/blob/master/wiring.md).

For other technical issues or questions, please [submit an issue](https://github.com/MorganKryze/Carousel/issues) on the repository.

## Contributing

If you want to contribute to the project, you can follow the steps described in the [CONTRIBUTING](./.github/CONTRIBUTING.md) file and get in touch with us at this email: [morgan@kodelab.fr](mailto:morgan@kodelab.fr).

## Acknowledgments

We would like to express our gratitude to the following individuals for their contributions to the start of the project:

- [Allen's lab](https://github.com/allenslab): for the `matrix-dashboard` project, which is a great starting point for building a dashboard using the Matrix platform through his [video](https://www.youtube.com/watch?v=A5A6ET64Oz8).
- [Ty Porter](https://github.com/ty-porter): for bringing public [Allen's lab's project](https://github.com/ty-porter/matrix-dashboard) source code and making it available to the community.
- [Henner Zeller](https://github.com/hzeller): for the `rpi-rgb-led-matrix` library, which is the core of the communication between the Raspberry Pi and the led matrix.
- [Milk And Espresso](https://m.twitch.tv/milkandespresso/about): for making some of the original background images.

Finally, we would like to thank all the people who tried the project and gave us feedback to improve it.

## License

This project is licensed by the [original author](https://github.com/allenslab) under the GNU GPL v3, which allows you to _use_, _modify_, and _distribute_ the software freely, as long as you **provide the source code** and do not add restrictions that limit others' rights under the same license. For full details, refer to the [LICENSE](LICENSE) file.

[^1]: The weather app is compatible with the [OpenWeatherMap API](https://openweathermap.org/) or [AccuWeather API](https://developer.accuweather.com/). You will need to create an account on their website to get an API key. Although AccuWeather won't require you to enter your credit card details.
[^2]: The Notion todo lists app is compatible with the [Notion API](https://developers.notion.com/). You will need to create an account on their website to get an API key.
[^3]: The Spotify player app is compatible with the [Spotify API](https://developer.spotify.com/). You will need to create an account on their website to get an API key.
