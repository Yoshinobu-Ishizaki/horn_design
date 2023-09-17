# 4th valve location pattern for double horn
Yoshinobu Ishizaki
2023-09-17

``` r
library(tidyverse)
```

    ── Attaching core tidyverse packages ──────────────────────── tidyverse 2.0.0 ──
    ✔ dplyr     1.1.3     ✔ readr     2.1.4
    ✔ forcats   1.0.0     ✔ stringr   1.5.0
    ✔ ggplot2   3.4.3     ✔ tibble    3.2.1
    ✔ lubridate 1.9.2     ✔ tidyr     1.3.0
    ✔ purrr     1.0.2     
    ── Conflicts ────────────────────────────────────────── tidyverse_conflicts() ──
    ✖ dplyr::filter() masks stats::filter()
    ✖ dplyr::lag()    masks stats::lag()
    ℹ Use the conflicted package (<http://conflicted.r-lib.org/>) to force all conflicts to become errors

## Create design pattern

Compared to 1-2-3 valves, 4th valve can be located at,

- thumb/pinkey finger side
- inline/offset
- flat/step level

and a valve rotation can be

- 90 degree
- 60 degree
- 120 degree

Compose a table with these layout combinations.

``` r
s1 <- c("thumb","pinkey")
s2 <- c("inline","offset")
s3 <- c("flat","step")
s4 <- c("90deg","60deg","120deg")
```

``` r
v4tab <- expand_grid(s1,s2,s3,s4)
names(v4tab) <- c("Side","Align","Level","Rotation")
v4tab$Ex = ""
```

In case of 60 degree rotation, a valve does not have 2 levels, so that
level difference is meaningless.

``` r
v4tab <- 
  v4tab |> filter(!(Level == "flat" & Rotation == "60deg"))
```

## Existing example

There are some type of horn with one of such combination.

``` r
v4tab <- 
  v4tab |> mutate(Ex = if_else(Side == "thumb" & Align == "offset" & Level == "step"& Rotation == "60deg", "Alexander 103", Ex) )
```

``` r
v4tab <- 
  v4tab |> mutate(Ex = if_else(Side == "pinkey" & Align == "inline" & Level == "flat"& Rotation == "120deg", "Geyer; Yamaha 871", Ex))
```

``` r
v4tab <- 
  v4tab |> mutate(Ex = if_else(Side == "pinkey" & Align == "inline" & Level == "flat" & Rotation == "90deg", "Knopf; Paxman; E.Schmid", Ex))
```

``` r
v4tab <- 
  v4tab |> mutate(Ex = if_else(Side == "thumb" & Align == "offset" & Level == "step"& Rotation == "120deg", "Conn 8D; Yamaha 668-2; Hans Hoyer 6801", Ex))
```

``` r
v4tab <- 
  v4tab |> mutate(Ex = if_else(Side == "thumb" & Align == "offset" & Level == "step"& Rotation == "90deg", "Yamaha 868-1", Ex))
```

``` r
v4tab <- 
  v4tab |> mutate(Ex = if_else(Side == "thumb" & Align == "offset" & Level == "step"& Rotation == "90deg", "Kruspe; Klaus Fehr", Ex))
```

``` r
v4tab <- 
  v4tab |> mutate(Ex = if_else(Side == "thumb" & Align == "inline" & Level == "flat" & Rotation == "90deg", "Yamaha 869", Ex))
```

## View table

``` r
v4tab
```

| Side   | Align  | Level | Rotation | Ex                                     |
|:-------|:-------|:------|:---------|:---------------------------------------|
| thumb  | inline | flat  | 90deg    | Yamaha 869                             |
| thumb  | inline | flat  | 120deg   |                                        |
| thumb  | inline | step  | 90deg    |                                        |
| thumb  | inline | step  | 60deg    |                                        |
| thumb  | inline | step  | 120deg   |                                        |
| thumb  | offset | flat  | 90deg    |                                        |
| thumb  | offset | flat  | 120deg   |                                        |
| thumb  | offset | step  | 90deg    | Kruspe; Klaus Fehr                     |
| thumb  | offset | step  | 60deg    | Alexander 103                          |
| thumb  | offset | step  | 120deg   | Conn 8D; Yamaha 668-2; Hans Hoyer 6801 |
| pinkey | inline | flat  | 90deg    | Knopf; Paxman; E.Schmid                |
| pinkey | inline | flat  | 120deg   | Geyer; Yamaha 871                      |
| pinkey | inline | step  | 90deg    |                                        |
| pinkey | inline | step  | 60deg    |                                        |
| pinkey | inline | step  | 120deg   |                                        |
| pinkey | offset | flat  | 90deg    |                                        |
| pinkey | offset | flat  | 120deg   |                                        |
| pinkey | offset | step  | 90deg    |                                        |
| pinkey | offset | step  | 60deg    |                                        |
| pinkey | offset | step  | 120deg   |                                        |

So, out of 20 possible combinations, there are many unused pattern.

Can we create a new model to fill one of this?
