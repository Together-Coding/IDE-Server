let hostname = ''

let chart;
const chartName = 'Websocket Communication'
let nodeNames = new Set()

let colorIdx = 0;

let pendingEdges = []
let addNodeInterval = null;
let nodeTable = {};  // map ID to node

const color = () => {
    return Highcharts.getOptions().colors[colorIdx++ % Highcharts.getOptions().colors.length]
}

const beforeCreate = () => {
    Highcharts.setOptions({
        colors: [
            '#058DC7', '#50B432', '#ED561B', '#DDDF00', '#22c9b3',
            '#24CBE5', '#64E572', '#FF9655', '#FFF263', '#6AF9C4',
            '#bd20ad', '#3731ad', '#4a8c76', '#67b528', '#38c96b',
            '#e89207', '#eb4034', '#ff0073', '#5d00ff', '#cc6825',
        ]
    })
}

const createGraph = (_hostname) => {
    hostname = _hostname
    beforeCreate();

    chart = Highcharts.chart('container', {
        chart: {
            type: 'networkgraph',
            marginTop: 60,
            height: 800,
        },
        title: {
            text: chartName,
        },
        tooltip: {
            enabled: false,
        },
        credits: {
            enabled: true,
            href: "https://together-coding.com",
            text: "Together-Coding",
        },
        plotOptions: {
            networkgraph: {
                keys: ['from', 'to'],
                layoutAlgorithm: {
                    integration: 'verlet',
                    enableSimulation: true,
                    // enableSimulation: false,
                    // initialPositions: 'circle', // default 'circle'
                    initialPositions: 'random', // default 'circle'
                    // gravitationalConstant: 0.0625, // default 0.0625
                    // linkLength: 240, // default undefined
                    // maxSpeed: 5, // default 10
                }
            }
        },
        series: [{
            id: chartName,
            marker: {
                radius: 13,
            },
            dataLabels: {
                enabled: true,
                textPath: {
                    enabled: false,
                },
                linkFormat: '',
                allowOverlap: true
            },
            data: []
        }]
    })

    addEdge(hostname, hostname);
}


/**
 * Used to prevent same edges from being added.
 * @returns
 */
const startProcessEdge = () => {
    if (addNodeInterval != null) return;

    addNodeInterval = setInterval(() => {
        if (pendingEdges.length === 0) {
            clearInterval(addNodeInterval);
            addNodeInterval = null;
            return;
        }

        let edge = pendingEdges.shift()
        chart.series[0].addPoint(edge);

        // Set color for the new nodes
        chart.series[0].nodes.forEach(node => {
            if (!nodeNames.has(node.id)) {
                nodeNames.add(node.id);
                nodeTable[node.id] = node;

                if (node.id.toLowerCase().startsWith('s-')) {
                    node.marker = Object.assign(node.marker || {}, { radius: 20 })
                    node.color = '#000000';
                } else {
                    node.name = node.id.slice(0, 3)
                    node.color = color();
                }
            }
        })
    }, 50)
}

/**
 * Add new edge
 * @param {string} from_ link from
 * @param {string} to_ link to
 * @returns 
 */
const addEdge = (from_, to_) => {
    const newNodes = new Set([from_, to_].filter(x => !nodeNames.has(x)))
    if (newNodes.size === 0) return;

    pendingEdges.push({
        from: from_,
        to: to_,
    });
    startProcessEdge();
}

/**
 * Remove node incrementally
 * @param {*} node 
 */
const removeNode = (node) => {
    const step = 0.5;
    const decInterval = 200;  // milliseconds
    const need = 2500
    const colorThres = 230;
    const linkColor = `rgb(${colorThres},${colorThres},${colorThres})`;

    node.dataLabel.css({ 'visibility': 'hidden' })  // The other options does not work. :(

    // Change link color
    for (let link of [...node.linksFrom, ...node.linksTo]) {
        link.graphic.element.style.stroke = linkColor;
    }

    const remove = () => {
        nodeNames.delete(node.id);
        delete nodeTable[node.id];
        if (node && node.series && node.remove) node.remove()
    };

    const clear = () => {
        clearInterval(interval);
        interval = null;
    }

    // Increase color incrementally
    let interval = setInterval(() => {
        if (!node || !node.series || node.series.opacity <= 0) {
            return clear()
        }
        let [r, g, b] = node.color.slice(1).match(/.{1,2}/g)
            .map(c => {
                let v = parseInt(c, 16)
                if (v <= colorThres) return parseInt(v + (colorThres - v) * step + 1).toString(16)
                return v.toString(16)
            });

        node.color = `#${r}${g}${b}`;
    }, decInterval)

    setTimeout(() => {
        clear();
        remove()
    }, need)
}

/**
 * Because all series in one networkgraph share plot options. (https://github.com/highcharts/highcharts/issues/15163), we cannot handle another series for disconnected nodes.
 * Thus, increase node's color incrementally, and finally remove it.
 * @param {*} name 
 */
const dropNode = (name) => {
    chart.series[0].nodes.forEach(node => {
        if (node.id == name) removeNode(node);
    })
}

