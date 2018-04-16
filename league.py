from bs4 import BeautifulSoup
import requests, pickle, sys, numpy

ROOT_URL = 'https://www.basketball-reference.com'
LAST_YEAR = 2018
LOG_FILE = 'log.txt'
SAVE_DIR = 'data/'
OFFLINE_PAGES = 'offline_pages/'
CATERGORIES = (
    'fg_pct', 
    'ft_pct',
    'pts', 
    'trb', 
    'ast', 
    'fg3', 
    'stl', 
    'blk',
    'tov'
)

MEANS = {
    'fg_pct': 0.4520048309178744, #fix this 
    'ft_pct': 0.7212995169082126, #and this
    'pts': 571.3220611916264,
    'trb': 237.743961352657, 
    'ast': 127.23349436392914,
    'fg3': 54.86151368760064,
    'stl': 43.391304347826086,
    'blk': 27.43317230273752,
    'tov': 75.53462157809984
}

DEVIATIONS = { #Pulled from calcDeviations
    'fg_pct': 0.1311215646297807,
    'ft_pct': 0.22473424022081043,
    'pts': 509.81549753433967,
    'trb': 213.96595621370744,
    'ast': 143.3842800329773, 
    'fg3': 61.500377572085455,
    'stl': 37.40895362963546,
    'blk': 33.52299849027061,
    'tov': 68.3569595733988
}


class League:
    def __init__(self):
        self.teams = []
        self.allPlayers = []
    def viewTeams(self):
        print(self.teams)

class Team:
    def __init__(self):
        self.roster = []

class Player:
    def __init__(self, name):
        print("Created {0}.".format(name))
        self.name = str(name)
        self.totals = []
    @property
    def lastYearTotals(self):
        self.totals = [i for i in self.totals if i]
        return self.totals[0]
    def getLastYearStat(self, stat):
        if len(self.totals) > 0:
            return self.totals[0].get(stat, 0)
        return 0
    def getBestYearStat(self, stat):
        if len(self.totals) > 0:
            if stat == 'tov':
                return min([d.get(stat, 0) for d in self.totals])
            return max([d.get(stat, 0) for d in self.totals])
        return 0
    def getSigma(self, stat):
        if len(self.totals) > 0:
            val = self.getBestYearStat(stat)
            diff = val - MEANS[stat]
            if stat == 'tov':
                diff = -1 * diff
            sigmas = diff / DEVIATIONS[stat]
            return sigmas
        return -99999999
    def getTotalSigmas(self):
        if len(self.totals) > 0:
            total = 0
            for stat in ('pts', 'trb', 'ast', 'fg3', 'stl', 'blk', 'fg_pct', 'ft_pct'):
                total += self.getSigma(stat)
            for stat in ('tov',):
                total += self.getSigma(stat)
            return total
        return 0
    def getTotalFantasyPoints(self): #Crude totals
        if len(self.totals) > 0:
            total = 0
            for stat in ('pts', 'trb', 'ast', 'fg3', 'stl', 'blk'):
                total += max([d.get(stat, 0) for d in self.totals])
            for stat in ('fg_pct', 'ft_pct'):
                total *= max([d.get(stat, 0) for d in self.totals])
            for stat in ('tov',):
                total -= min([d.get(stat, 0) for d in self.totals])
            return total
        return 0
    def __str__(self):
        return '{0}'.format(self.name)
    def __repr__(self):
        return 'Player {0}'.format(self.name)

def playerFromURL(url):
    #on BBR, the table is commented out.. maybe to stop scrapers like me.
    html = ''
    name = ''
    try:
        filename = OFFLINE_PAGES + url.split('/')[-1]
        with open(filename, "r") as f:
            html = f.read()
            f.close()
            print("Reading from file", filename)
    except:
        html = requests.get(url).text
        print("Falling back and downloading from URL", url)
    try:
        html = html.replace('<!--', '<div>').replace('--!>', '</div>') #fuck you!
        soup = BeautifulSoup(html, 'lxml')
        name = soup.find('h1', {'itemprop': 'name'}).contents[0]
        p = Player(name)
        i = 0
        while i <= 2:
            currentYear = LAST_YEAR - i
            tableRow = soup.find('tr', {'id': 'totals.{0}'.format(currentYear)})
            if tableRow:
                rowDict = {}
                for col in tableRow:
                    contents = col.contents
                    if len(contents) > 0:
                        contents = contents[0]
                        if contents.name in ('a', 'strong'):
                            contents = contents.contents[0]
                    else:
                        contents = 0
                    contents = str(contents)
                    try:
                        contents = float(contents)
                    except:
                        contents = str(contents)
                    rowDict[str(col['data-stat'])] = contents
                p.totals.append(rowDict)
            i += 1
        return p
    except Exception as e: 
        write_log("URL read from {0} ({1}) failed".format(name, url))
        write_log(str(e) + "\n")

def parseFile(path):
    result = []
    with open(path, 'r') as f:
        result = f.read().split('\n')
    return result

def downloadAll():
    for linkLocation in parseFile("playerURLs.txt"):
        try:
            pageHTML = requests.get(linkLocation).text
            with open(OFFLINE_PAGES + linkLocation.split("/")[-1], "w") as f:
                f.write(pageHTML)
                f.close()
            print("Wrote {0} to offline file".format(linkLocation))
        except:
            write_log("failed at " + linkLocation)

def getAllActivePlayerURLS():
    alph = 'abcdefghijklmnopqrstuvwxyz'
    baseurl = ROOT_URL + '/players/{0}/'
    letterPages = [baseurl.format(ch) for ch in alph]
    names = []
    urls = []
    for url in letterPages:
        soup = BeautifulSoup(requests.get(url).text, 'lxml')
        for link in soup.find_all('a'):
            if link.parent.name == 'strong':
                linkLocation = ROOT_URL + link['href']
                playerName = link.contents[0]
                print("Found url:", linkLocation)
                names.append(playerName)
                urls.append(linkLocation)
    with open('playerURLs.txt', 'w') as f:
        f.write('\n'.join(urls))
        f.close()
    return urls

def save(lg, filename):
    savefile = open(SAVE_DIR + filename, "wb")
    pickle.dump(lg, savefile)
    savefile.close()

def load(filename):
    try:
        savefile = open(SAVE_DIR + filename, "rb")
        return pickle.load(savefile)
    except:
        return False

def write_log(l):
    with open(LOG_FILE, "a") as f:
        f.write("\n" + l)
        f.close()
    print("Wrote \"", l, "\"to log")

def allPlayers():
    result = load("playersList.dat")
    if result:
        return result
    result = []
    urls = parseFile("playerURLs.txt")
    for url in urls:
        result.append(playerFromURL(url))
    save(result, "playersList.dat")
    return result

def calcDeviations():
    devs = {}
    means = {}
    players = allPlayers()
    for cat in CATERGORIES:
        arr = numpy.array([p.getBestYearStat(cat) for p in players])
        devs[cat] = numpy.std(arr)
        means[cat] = numpy.mean(arr)
    print(devs)
    print(means)


def sigmaRank():
    players = allPlayers()
    players = sorted(players, key=lambda p: p.getTotalSigmas())
    points = reversed(['{0} ({1})'.format(p.name, p.getTotalSigmas()) for p in players])
    i = 1
    for player in points:
        print(i, player)
        i += 1
