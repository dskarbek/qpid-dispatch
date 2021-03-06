/*
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.
*/
/**
 * @module QDR
 */
var QDR = (function (QDR) {

  /**
   * @method ChartsController
   *
   * Controller that handles the QDR charts page
   */
  QDR.module.controller("QDR.ChartsController", function($scope, QDRService, QDRChartService, $dialog, $location, $routeParams) {

	var updateTimer = null;

	if (!QDRService.connected) {
		// we are not connected. we probably got here from a bookmark or manual page reload
		QDRService.redirectWhenConnected("charts");
		return;
	}
	// we are currently connected. setup a handler to get notified if we are ever disconnected
	QDRService.addDisconnectAction( function () {
		QDRService.redirectWhenConnected("charts")
		$scope.$apply();
	})


    $scope.svgCharts = [];
    // create an svg object for each chart
    QDRChartService.charts.filter(function (chart) {return chart.dashboard}).forEach(function (chart) {
        var svgChart = new QDRChartService.AreaChart(chart)
        svgChart.zoomed = false;
        $scope.svgCharts.push(svgChart);
    })

    // redraw the chart every update period
	// this is a $scope function because it is called from the dialog
    var updateCharts = function () {
        $scope.svgCharts.forEach(function (svgChart) {
            svgChart.tick(svgChart.chart.id()); // on this page we are using the chart.id() as the div id in which to render the chart
        })
		var updateRate = localStorage['updateRate'] ?  localStorage['updateRate'] : 5000;
		if (updateTimer) {
			clearTimeout(updateTimer)
		}
        updateTimer = setTimeout(updateCharts, updateRate);
    }

        // called by ng-init in the html when the page is loaded
	$scope.chartsLoaded = function () {
	    $scope.svgCharts.forEach(function (svgChart) {
                QDRChartService.sendChartRequest(svgChart.chart.request(), true);
            })
            if (updateTimer)
                clearTimeout(updateTimer)
	    setTimeout(updateCharts, 0);
	}

	$scope.zoomChart = function (chart) {
		chart.zoomed = !chart.zoomed;
		chart.zoom(chart.chart.id(), chart.zoomed);
	}
    $scope.showListPage = function () {
        $location.path("/list");
    };

    $scope.hasCharts = function () {
        return QDRChartService.numCharts() > 0;
    };

    $scope.editChart = function (chart) {
        doDialog("chart-config-template.html", chart.chart);
    };

    $scope.delChart = function (chart) {
        QDRChartService.unRegisterChart(chart.chart);
        // remove from svgCharts
        $scope.svgCharts.forEach(function (svgChart, i) {
            if (svgChart === chart) {
                delete $scope.svgCharts.splice(i, 1);
            }
        })
    };

    // called from dialog when we want to clone the dialog chart
    // the chart argument here is a QDRChartService chart
    $scope.addChart = function (chart) {
        $scope.svgCharts.push(new QDRChartService.AreaChart(chart));
    };

    $scope.$on("$destroy", function( event ) {
        if (updateTimer) {
            clearTimeout(updateTimer);
            updateTimer = null;
        }
        for (var i=$scope.svgCharts.length-1; i>=0; --i) {
            delete $scope.svgCharts.splice(i, 1);
        }
    });

    function doDialog(template, chart) {

	    $dialog.dialog({
			backdrop: true,
			keyboard: true,
			backdropClick: true,
			templateUrl: template,
			controller: "QDR.ChartDialogController",
			resolve: {
				chart: function() {
					return chart;
				},
				updateTick: function () {
					return updateCharts;
				},
				dashboard: function () {
       	            return $scope;
       	        }
			}
	    }).open();
    };

  });

  QDR.module.controller("QDR.ChartDialogController", function($scope, QDRChartService, $location, dialog, $rootScope, chart, updateTick, dashboard) {
        var dialogSvgChart = null;
        $scope.svgDivId = "dialogChart";    // the div id for the svg chart

	var updateTimer = null;
        $scope.chart = chart;  // the underlying chart object from the dashboard
        $scope.dialogChart = $scope.chart.copy(); // the chart object for this dialog
        $scope.userTitle = $scope.chart.title();

        $scope.$watch('userTitle', function(newValue, oldValue) {
            if (newValue !== oldValue) {
                $scope.dialogChart.title(newValue);
                dialogSvgChart.tick($scope.svgDivId);
            }
        })
		$scope.$watch("dialogChart.areaColor", function (newValue, oldValue) {
			if (newValue !== oldValue) {
				if (dialogSvgChart)
                    dialogSvgChart.tick($scope.svgDivId);
			}
		})
		$scope.$watch("dialogChart.lineColor", function (newValue, oldValue) {
			if (newValue !== oldValue) {
				if (dialogSvgChart)
                    dialogSvgChart.tick($scope.svgDivId);
			}
		})
		$scope.$watch("dialogChart.type", function (newValue, oldValue) {
			if (newValue !== oldValue) {
				if (dialogSvgChart)
                    dialogSvgChart.tick($scope.svgDivId);
			}
		})

        // the stored rateWindow is in milliseconds, but the slider is in seconds
        $scope.rateWindow = $scope.chart.rateWindow / 1000;

		var cleanup = function () {
			if (updateTimer) {
				clearTimeout(updateTimer);
				updateTimer = null;
			}
			QDRChartService.unRegisterChart($scope.dialogChart);     // remove the chart
		}
		$scope.okClick = function () {
		    cleanup();
	            dialog.close();
	    };

		var initRateSlider = function () {
			if (document.getElementById('rateSlider')) {
				$( "#rateSlider" ).slider({
				      value: $scope.rateWindow,
				      min: 1,
				      max: 10,
				      step: 1,
				      slide: function( event, ui ) {
						$scope.rateWindow = ui.value;
						$scope.dialogChart.rateWindow = ui.value * 1000;
						$scope.$apply();
						if (dialogSvgChart)
							dialogSvgChart.tick($scope.svgDivId);
				      }
				});

			} else {
				setTimeout(initRateSlider, 100)
			}
		}
		initRateSlider();

		var initDurationSlider = function () {
			if (document.getElementById('durationSlider')) {
				$( "#durationSlider" ).slider({
				      value: $scope.dialogChart.visibleDuration,
				      min: 1,
				      max: 10,
				      step: 1,
				      slide: function( event, ui ) {
						$scope.visibleDuration = $scope.dialogChart.visibleDuration = ui.value;
						$scope.$apply();
						if (dialogSvgChart)
							dialogSvgChart.tick($scope.svgDivId);
				      }
				});

			} else {
				setTimeout(initDurationSlider, 100)
			}
		}
		initDurationSlider();

        // handle the Apply button click
        // update the dashboard chart's properties
        $scope.apply = function () {
            $scope.chart.areaColor = $scope.dialogChart.areaColor;
            $scope.chart.lineColor = $scope.dialogChart.lineColor;
            $scope.chart.type = $scope.dialogChart.type;
            $scope.chart.rateWindow = $scope.rateWindow * 1000;
            $scope.chart.title($scope.dialogChart.title());
            $scope.chart.visibleDuration = $scope.dialogChart.visibleDuration;
            QDRChartService.saveCharts();
			if (typeof updateTick === "function")
				updateTick();
	    if (typeof updateTick === "function")
		updateTick();
        }

        // add a new chart to the dashboard based on the current dialog settings
        $scope.copyToDashboard = function () {
            var chart = $scope.dialogChart.copy();
            // set the new chart's dashboard state
            QDRChartService.addDashboard(chart);
            // notify the chart controller that it needs to display a new chart
            dashboard.addChart(chart);
        }

        // update the chart on the popup dialog
        var updateDialogChart = function () {
            // draw the chart using the current data
            if (dialogSvgChart)
                dialogSvgChart.tick($scope.svgDivId);

            // draw the chart again in 1 second
			var updateRate = localStorage['updateRate'] ? localStorage['updateRate'] : 5000;
			if (updateTimer)
				clearTimeout(updateTimer);
            updateTimer = setTimeout(updateDialogChart, updateRate);
        }

        var showChart = function () {
            // ensure the div for our chart is loaded in the dom
            var div = angular.element("#dialogChart");
            if (!div.width()) {
                setTimeout(showChart, 100);
                return;
            }
            dialogSvgChart = new QDRChartService.AreaChart($scope.dialogChart);
			$('input[name=lineColor]').val($scope.dialogChart.lineColor);
			$('input[name=areaColor]').val($scope.dialogChart.areaColor);
			$('input[name=areaColor]').on('input', function (e) {
				$scope.dialogChart.areaColor = $(this).val();
				updateDialogChart()
			})
			$('input[name=lineColor]').on('input', function (e) {
				$scope.dialogChart.lineColor = $(this).val();
				updateDialogChart()
			})
			if (updateTimer)
				clearTimeout(updateTimer);
            updateDialogChart();
        }
        showChart();


  });

  return QDR;

}(QDR || {}));

